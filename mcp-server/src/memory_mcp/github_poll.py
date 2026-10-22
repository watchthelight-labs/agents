"""Polls the GitHub threads, repos and searches we follow and records what other people said.

Runs as a oneshot (memory-mcp poll, memory-mcp-poll.timer). Requests are conditional (ETag) and paced; no database
lock is held across a request. A follow's first look records the existing history as seen, so seeding does not flood
the inbox. The token is read-only; this module never writes to GitHub.
"""

from datetime import datetime, timedelta, timezone
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .contacts import THREAD_COLS, parse_url, _utc
from .store import now

API = "https://api.github.com"
CADENCE_BY_AGE = ((7, 30), (30, 180), (90, 1440))   # days since activity -> minutes between checks
CLOSED_CADENCE, CLOSED_RETIRE_DAYS = 7 * 1440, 90
FIRST_SEARCH_DAYS = 30


class Response:
    def __init__(self, status, body, headers):
        self.status, self.body, self.headers = status, body, {k.lower(): v for k, v in (headers or {}).items()}

    def json(self):
        return json.loads(self.body) if self.body else None


def urllib_transport(url, headers, timeout=15):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, r.read().decode("utf-8", "replace"), dict(r.headers))
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {}))


class RateLimited(Exception):
    def __init__(self, until):
        super().__init__(f"rate limited until {until}")
        self.until = until


class GitHub:
    def __init__(self, token, transport=urllib_transport, pause=0.3, budget=400, floor=200, sleep=time.sleep):
        self.token, self.transport, self.pause, self.budget, self.floor, self.sleep = token, transport, pause, budget, floor, sleep
        self.requests = self.not_modified = 0
        self.rate_remaining = None

    def get(self, path, params=None, etag=None):
        if self.requests >= self.budget:
            raise RateLimited(None)
        url = path if path.startswith("http") else API + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "watchthelight-memory-poller"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if etag:
            headers["If-None-Match"] = etag
        if self.requests:
            self.sleep(self.pause)
        self.requests += 1
        r = self.transport(url, headers)
        if r.headers.get("x-ratelimit-remaining") is not None:
            self.rate_remaining = int(r.headers["x-ratelimit-remaining"])
        if r.status == 304:
            self.not_modified += 1
        if r.status in (403, 429) and (r.headers.get("retry-after") or self.rate_remaining == 0):
            raise RateLimited(self._reset(r))
        if self.rate_remaining is not None and self.rate_remaining < self.floor and "/search/" not in url:
            raise RateLimited(self._reset(r))
        return r

    @staticmethod
    def _reset(r):
        if r.headers.get("retry-after"):
            return _utc(datetime.now(timezone.utc) + timedelta(seconds=int(r.headers["retry-after"])))
        if r.headers.get("x-ratelimit-reset"):
            return _utc(datetime.fromtimestamp(int(r.headers["x-ratelimit-reset"]), timezone.utc))
        return _utc(datetime.now(timezone.utc) + timedelta(hours=1))

    def pages(self, path, params, limit=5, stop=None):
        """GET with Link paging; returns (items, last response). stop(batch) ends paging early."""
        items, url, r = [], path, None
        for _ in range(limit):
            r = self.get(url, params)
            if r.status != 200:
                break
            data = r.json()
            batch = data.get("items", []) if isinstance(data, dict) else data
            items += batch
            if stop and stop(batch):
                break
            nxt = [p.split(";")[0].strip(" <>") for p in r.headers.get("link", "").split(",") if 'rel="next"' in p]
            if not nxt:
                break
            url, params = nxt[0], None
        return items, r


def _when(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _is_bot(user):
    login = (user or {}).get("login") or ""
    return (user or {}).get("type") == "Bot" or login.endswith("[bot]")


class Poller:
    def __init__(self, contacts, gh, self_logins=("watchthelight",), dry_run=False, log=print):
        self.c, self.store, self.gh = contacts, contacts.store, gh
        self.self_logins = {s.strip().lower() for s in self_logins if s.strip()}
        self.dry_run, self.log = dry_run, log
        self.errors, self.new_events = [], 0

    # ---------- events ----------

    def _event(self, kind, user, ts, body, url, external_id, summary=""):
        login = ((user or {}).get("login") or "").lower()
        mine = login in self.self_logins
        excerpt = None if mine else self.c.clean(" ".join((body or "").split()), 280)
        return {"kind": kind, "author": login or None, "direction": "out" if mine else "in", "ts": ts, "url": url,
                "external_id": external_id, "excerpt": excerpt, "summary": summary}

    def _comments(self, repo, number, since, is_pr):
        params = {"per_page": 100}
        if since:
            params["since"] = since
        out = []
        items, _ = self.gh.pages(f"/repos/{repo}/issues/{number}/comments", params)
        out += [self._event("comment", i.get("user"), i["created_at"], i.get("body"), i.get("html_url"), f"gh:ic:{i['id']}")
                for i in items if not _is_bot(i.get("user"))]
        if is_pr:
            items, _ = self.gh.pages(f"/repos/{repo}/pulls/{number}/comments", params)
            out += [self._event("review_comment", i.get("user"), i["created_at"], i.get("body"), i.get("html_url"),
                                f"gh:rc:{i['id']}") for i in items if not _is_bot(i.get("user"))]
            items, _ = self.gh.pages(f"/repos/{repo}/pulls/{number}/reviews", {"per_page": 100})
            for i in items:
                ts = i.get("submitted_at")
                if not ts or _is_bot(i.get("user")) or (since and ts <= since):
                    continue
                if not (i.get("body") or "").strip() and i.get("state") not in ("APPROVED", "CHANGES_REQUESTED"):
                    continue
                out.append(self._event("review", i.get("user"), ts, i.get("body"), i.get("html_url"), f"gh:rv:{i['id']}",
                                       summary=(i.get("state") or "").lower()))
        return out

    # ---------- per kind ----------

    def poll_issue(self, f):
        repo, _, number = f["target"].partition("#")
        r = self.gh.get(f"/repos/{repo}/issues/{number}", etag=f["etag"])
        if r.status == 304:
            return {"follow": {"fail_count": 0, "last_error": None}, "reschedule": True}
        if r.status in (404, 410):
            fails = f["fail_count"] + 1
            return {"follow": {"fail_count": fails, "last_error": f"HTTP {r.status}", "active": 0 if fails >= 3 else 1},
                    "remote_state": "gone" if fails >= 3 else None, "reschedule": True}
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} for {f['target']}")
        data = r.json()
        is_pr = "pull_request" in data
        merged = bool((data.get("pull_request") or {}).get("merged_at"))
        remote = "merged" if merged else data.get("state")
        if data.get("locked") and remote == "open":
            remote = "locked"
        parsed = parse_url(data.get("html_url"))
        result = {"data": data, "parsed": parsed, "remote_state": remote, "etag": r.headers.get("etag"),
                  "kind": "pr" if is_pr else "issue", "events": [], "follow": {"fail_count": 0, "last_error": None}}
        if parsed["repo"] and f"{parsed['repo']}#{parsed['number']}" != f["target"]:
            result["follow"]["target"] = f"{parsed['repo']}#{parsed['number']}"   # moved or renamed repo
        cursor = f["cursor"]
        if cursor is None or data.get("updated_at", "") > cursor:
            if cursor is None:
                result["events"].append(self._event("opened", data.get("user"), data["created_at"], data.get("body"),
                                                    data.get("html_url"), f"gh:op:{parsed['repo']}#{parsed['number']}",
                                                    summary="opened"))
            since = None if cursor is None else _utc(datetime.fromisoformat(cursor.replace("Z", "+00:00")) - timedelta(seconds=1))
            result["events"] += self._comments(repo, number, since, is_pr)
            result["follow"]["cursor"] = data.get("updated_at")
        return result

    def poll_release(self, f):
        r = self.gh.get(f"/repos/{f['target']}/releases", {"per_page": 5}, etag=f["etag"])
        if r.status == 304:
            return {"follow": {"fail_count": 0, "last_error": None}, "reschedule": True}
        if r.status in (404, 410):
            fails = f["fail_count"] + 1
            return {"follow": {"fail_count": fails, "last_error": f"HTTP {r.status}", "active": 0 if fails >= 3 else 1},
                    "reschedule": True}
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} for {f['target']}")
        events = [self._event("release", rel.get("author"), rel.get("published_at") or rel.get("created_at"), "",
                              rel.get("html_url"), f"gh:rel:{rel['id']}",
                              summary=f"{f['target']} {rel.get('tag_name')}: {(rel.get('name') or '')[:100]}")
                  for rel in r.json() if not rel.get("draft")]
        for e in events:
            e["direction"], e["excerpt"] = "in", None
        return {"releases": events, "etag": r.headers.get("etag"), "follow": {"fail_count": 0, "last_error": None}}

    def poll_search(self, f):
        # GitHub's updated: qualifiers proved unreliable, so sort by update time and cut off here instead
        since = f["cursor"] or _utc(datetime.now(timezone.utc) - timedelta(days=FIRST_SEARCH_DAYS))
        cut = _when(since)
        items, r = self.gh.pages("/search/issues", {"q": f["target"], "sort": "updated", "order": "desc", "per_page": 50},
                                 limit=4, stop=lambda batch: bool(batch) and _when(batch[-1]["updated_at"]) < cut)
        if r is not None and r.status not in (200, 304):
            raise RuntimeError(f"HTTP {r.status} for search {f['target'][:40]}")
        hits = [i for i in items if _when(i["updated_at"]) >= cut]
        newest = max((i["updated_at"] for i in hits), key=_when, default=None)
        return {"hits": hits, "follow": {"fail_count": 0, "last_error": None,
                                         "cursor": _utc(_when(newest)) if newest else f["cursor"]}}

    # ---------- apply ----------

    def _thread_for(self, con, f, result):
        if f["thread_id"]:
            t = self.c.thread_row(con, f["thread_id"])
            if t:
                return t
        parsed = result["parsed"]
        t = con.execute("SELECT * FROM threads WHERE external_key=?", (parsed["external_key"],)).fetchone()
        if t is None:
            parsed = {**parsed, "kind": result["kind"]}
            t = self.c.new_thread(con, parsed, result["data"].get("title"), "", "poller", project=f["project"])
        con.execute("UPDATE follows SET thread_id=? WHERE id=?", (t["id"], f["id"]))
        return t

    def _cadence(self, f, t, data):
        if t is None:
            return f["cadence_min"]
        if t["remote_state"] in ("closed", "merged", "gone"):
            return CLOSED_CADENCE
        last = max(x for x in (t["last_in_at"], t["last_out_at"], (data or {}).get("updated_at"), f["created_at"]) if x)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).days
        for days, minutes in CADENCE_BY_AGE:
            if age < days:
                return max(f["cadence_min"], minutes)
        return max(f["cadence_min"], 7 * 1440)

    def _insert(self, con, thread_id, e, baseline, origin="poller"):
        seen = now() if (e["direction"] == "out" or (baseline and e["ts"] < baseline)) else None
        pid = self.c.person(con, f"github:{e['author']}") if e["author"] and e["direction"] == "in" else None
        cur = con.execute("""INSERT OR IGNORE INTO interactions(thread_id,direction,kind,author,person_id,ts,summary,excerpt,
                             url,external_id,origin,seen_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (thread_id, e["direction"], e["kind"], e["author"], pid, e["ts"], e["summary"], e["excerpt"],
                           e["url"], e["external_id"], origin, seen, now()))
        if cur.rowcount and thread_id and pid:
            con.execute("INSERT OR IGNORE INTO thread_people(thread_id,person_id) VALUES (?,?)", (thread_id, pid))
        return cur.lastrowid if cur.rowcount else None, seen is None

    def apply(self, f, result):
        stamp = now()
        with self.store.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            f = con.execute("SELECT * FROM follows WHERE id=?", (f["id"],)).fetchone()
            sets = dict(result.get("follow", {}))
            if result.get("etag"):
                sets["etag"] = result["etag"]
            t = None
            new_ids, unread_new = [], 0
            before = None
            if "data" in result:
                t = self._thread_for(con, f, result)
                before = self.c._snap(t, THREAD_COLS)
                for e in sorted(result["events"], key=lambda e: e["ts"]):
                    iid, unread = self._insert(con, t["id"], e, f["baseline_before"])
                    if iid:
                        new_ids.append(iid)
                        unread_new += unread
                tsets = self._thread_update(con, t, result, unread_new)
                if tsets:
                    tsets["updated_at"] = stamp
                    con.execute("UPDATE threads SET " + ",".join(f"{k}=?" for k in tsets) + " WHERE id=?",
                                list(tsets.values()) + [t["id"]])
                t = self.c.thread_row(con, t["id"])
                if result.get("kind") and f["kind"] != result["kind"] and f["kind"] in ("issue", "pr"):
                    sets["kind"] = result["kind"]
            elif result.get("remote_state") and f["thread_id"]:
                con.execute("UPDATE threads SET remote_state=?,updated_at=? WHERE id=?", (result["remote_state"], stamp, f["thread_id"]))
            for e in result.get("releases", []):
                iid, unread = self._insert(con, None, e, f["baseline_before"])
                if iid:
                    new_ids.append(iid)
                    unread_new += unread
            for hit in result.get("hits", []):
                self._search_hit(con, f, hit)
            if t is None and f["thread_id"]:
                t = self.c.thread_row(con, f["thread_id"])
            cadence = self._cadence(f, t, result.get("data"))
            if t is not None and t["state"] == "closed" and t["remote_state"] in ("closed", "merged"):
                if self.c._days_since(t["updated_at"]) is not None and self.c._days_since(t["updated_at"]) > CLOSED_RETIRE_DAYS:
                    sets["active"] = 0
            sets.update(last_checked=stamp, updated_at=stamp,
                        next_check=_utc(datetime.now(timezone.utc) + timedelta(minutes=cadence)))
            con.execute("UPDATE follows SET " + ",".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [f["id"]])
            if unread_new or (t is not None and before and before["state"] != t["state"]):
                key = f"t:{t['id']}" if t is not None else f"f:{f['id']}"
                label = self.c.label(t) if t is not None else f["target"]
                self.c.memory._log(con, key, "ingest", "poller", "poller", f"ingest: {label} +{unread_new} new",
                                   before={"thread": before} if before else None,
                                   after={"thread": self.c._snap(t, THREAD_COLS) if t is not None else None,
                                          "interaction_ids": new_ids})
            self.new_events += unread_new
            if self.dry_run:
                con.rollback()
        return unread_new

    def _thread_update(self, con, t, result, unread_new):
        data, sets = result["data"], {}
        title = self.c.clean(data.get("title"), 200)
        if title and title != t["title"]:
            sets["title"] = title
        parsed = result["parsed"]
        if parsed["url"] and parsed["url"] != t["url"]:
            sets.update(url=parsed["url"], repo=parsed["repo"], number=parsed["number"], external_key=parsed["external_key"])
        if result["kind"] != t["kind"] and t["kind"] in ("issue", "pr", "other"):
            sets["kind"] = result["kind"]
        remote = result["remote_state"]
        state_event = remote != t["remote_state"] and t["remote_state"] is not None
        if remote != t["remote_state"]:
            sets["remote_state"] = remote
        last = con.execute("""SELECT direction,ts FROM interactions WHERE thread_id=? AND status='active' AND direction!='note'
                              ORDER BY ts DESC LIMIT 1""", (t["id"],)).fetchone()
        last_in = con.execute("SELECT max(ts) FROM interactions WHERE thread_id=? AND direction='in' AND status='active'",
                              (t["id"],)).fetchone()[0]
        last_out = con.execute("SELECT max(ts) FROM interactions WHERE thread_id=? AND direction='out' AND status='active'",
                               (t["id"],)).fetchone()[0]
        if last_in and last_in != t["last_in_at"]:
            sets["last_in_at"] = last_in
        if last_out and last_out != t["last_out_at"]:
            sets["last_out_at"] = last_out
        unread = self.c._unread(con, t["id"])
        state = t["state"]
        if t["state"] in ("closed", "dropped"):
            if unread_new:
                state = "waiting_on_us"
        elif t["state"] == "unlogged":
            pass
        elif unread:
            state = "waiting_on_us"
        elif remote in ("closed", "merged", "gone") and (state_event or t["state"] == "open"):
            state = "closed"
        elif (last and last["direction"] == "out" and t["state"] != "waiting_on_them"
              and (t["origin"] != "poller" or last_in)):  # our own tracking issue nobody else joined is not a follow-up
            state = "waiting_on_them"
            sets["next_check"] = _utc(datetime.now(timezone.utc) + timedelta(days=t["nudge_days"]))
        if state != t["state"]:
            sets["state"] = state
        return sets

    def _search_hit(self, con, f, hit):
        parsed = parse_url(hit.get("html_url"))
        if not parsed["external_key"] or parsed["platform"] != "github":
            return
        t = con.execute("SELECT * FROM threads WHERE external_key=?", (parsed["external_key"],)).fetchone()
        ours = f["target"].lower().startswith("org:")
        if t is None:
            state = "open" if ours else "unlogged"
            parsed = {**parsed, "kind": "pr" if "pull_request" in hit else "issue"}
            why = "" if not ours else "an issue on one of our repos"
            t = self.c.new_thread(con, parsed, hit.get("title"), why, "poller", state=state, project=f["project"])
        # history before the previous search counts as seen; anything newer is news
        baseline = f["cursor"] or now()
        existing = con.execute("SELECT id FROM follows WHERE target=? AND kind IN ('issue','pr','discussion')",
                               (f"{parsed['repo']}#{parsed['number']}",)).fetchone()
        if existing is None:
            stamp = now()
            con.execute("""INSERT INTO follows(thread_id,kind,target,project,cadence_min,next_check,baseline_before,origin,
                           created_at,updated_at) VALUES (?,?,?,?,30,?,?,'poller',?,?)""",
                        (t["id"], t["kind"] if t["kind"] in ("issue", "pr") else "issue",
                         f"{parsed['repo']}#{parsed['number']}", f["project"], stamp, baseline, stamp, stamp))
        else:
            con.execute("UPDATE follows SET active=1,next_check=? WHERE id=? AND active=0", (now(), existing[0]))

    # ---------- run ----------

    def run(self, only=None, limit=200):
        with self.store.connection() as con:
            last = con.execute("SELECT paused_until FROM poll_runs WHERE paused_until IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            if last and last[0] > now() and only is None:
                self.log(f"paused until {last[0]}")
                return {"paused_until": last[0]}
            run_id = None if self.dry_run else con.execute("INSERT INTO poll_runs(started_at) VALUES (?)", (now(),)).lastrowid
            if only is not None:
                due = con.execute("SELECT * FROM follows WHERE id=?", (only,)).fetchall()
            else:
                due = con.execute("SELECT * FROM follows WHERE active=1 AND next_check<=? ORDER BY next_check LIMIT ?",
                                  (now(), limit)).fetchall()
        paused = None
        for f in due:
            handler = {"issue": self.poll_issue, "pr": self.poll_issue, "release": self.poll_release,
                       "search": self.poll_search}.get(f["kind"])
            try:
                if handler is None:
                    result = {"follow": {"last_error": f"{f['kind']} polling is not supported yet"}}
                else:
                    result = handler(f)
                n = self.apply(f, result)
                if n:
                    self.log(f"{f['kind']} {f['target']}: {n} new")
            except RateLimited as e:
                paused = e.until
                self.errors.append("rate limited" + (f" until {e.until}" if e.until else " (budget)"))
                break
            except Exception as e:  # one bad follow must not stop the run
                self.errors.append(f"{f['kind']} {f['target']}: {e}"[:300])
                fails = f["fail_count"] + 1
                minutes = min(f["cadence_min"] * 2 ** fails, 1440)
                if not self.dry_run:
                    with self.store.connection() as con:
                        con.execute("UPDATE follows SET fail_count=?,last_error=?,next_check=?,updated_at=? WHERE id=?",
                                    (fails, str(e)[:300], _utc(datetime.now(timezone.utc) + timedelta(minutes=minutes)),
                                     now(), f["id"]))
        summary = {"follows_checked": len(due), "requests": self.gh.requests, "not_modified": self.gh.not_modified,
                   "new_events": self.new_events, "errors": self.errors, "rate_remaining": self.gh.rate_remaining,
                   "paused_until": paused}
        if run_id is not None:
            with self.store.connection() as con:
                con.execute("""UPDATE poll_runs SET finished_at=?,requests=?,not_modified=?,new_events=?,errors=?,
                               rate_remaining=?,paused_until=? WHERE id=?""",
                            (now(), self.gh.requests, self.gh.not_modified, self.new_events,
                             json.dumps(self.errors) if self.errors else None, self.gh.rate_remaining, paused, run_id))
        return summary
