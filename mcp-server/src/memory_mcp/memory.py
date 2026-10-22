"""Notes as working memory: typed and scoped, deduplicated on write, logged and revertible, assembled into boot context.

Every note write commits the source, its metadata and its change-log row in one SQLite transaction.
"""

from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
import json
import re
import time
import uuid

from .redact import scrub
from .store import now

TYPES = ("preference", "fact", "runbook", "decision", "gotcha", "open_loop", "session_digest")
REVIEW_DAYS = {"fact": 90, "runbook": 60, "gotcha": 180, "open_loop": 30}
DIGEST_BOOT_DAYS = 14
SENSITIVITY = ("normal", "private")
META_FIELDS = ("title", "type", "scope", "sensitivity", "status", "pinned", "verified_at", "review_by", "supersedes")
PROJECT_KEY = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
PART_LIMIT = 9200
PARTS = ("profile", "infra", "project", "threads", "people")
STOP = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is it its
just may me more most my no not of on once only or our out over own same she should so some such than that the their
them then there these they this those through to too under until up very was we were what when where which while who
why will with would you your yes also via per use used using about after again against all any because before
being below between both down during each few further here he her him his itself let off ours ourselves themselves
""".split())


def _today():
    return datetime.now(timezone.utc).date()


def _words(text):
    return {w for w in re.findall(r"[^\W_]+", (text or "").lower(), re.UNICODE) if len(w) > 2 and w not in STOP}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _norm_title(title):
    return " ".join(re.findall(r"[^\W_]+", (title or "").lower(), re.UNICODE))


def norm_path(path):
    return (path or "").strip().replace("\\", "/").rstrip("/").lower()


def norm_remote(remote):
    """git@github.com:a/b.git and https://github.com/a/b -> github.com/a/b"""
    r = (remote or "").strip().lower()
    r = re.sub(r"^(?:https?|ssh|git)://(?:[^@/]+@)?", "", r)
    r = re.sub(r"^[^@/]+@([^:/]+):", r"\1/", r)
    return r.removesuffix(".git").rstrip("/")


def check_scope(scope):
    if scope == "global":
        return scope
    if scope.startswith("project:") and PROJECT_KEY.fullmatch(scope[8:]):
        return scope
    raise ValueError("scope must be 'global' or 'project:<key>' (key: lowercase letters, digits, . _ -)")


class Memory:
    def __init__(self, store, vault=None, home_paths=("c:/users/agent", "~", "~")):
        self.store = store
        self.vault = vault
        self.home_paths = {norm_path(p) for p in home_paths}
        self._secrets = (0.0, None)
        self.contacts = None  # set by Contacts(store, memory)

    # ---------- helpers ----------

    def _secret_values(self):
        stamp, values = self._secrets
        if self.vault is None:
            return None
        if values is None or time.monotonic() - stamp > 60:
            values = self.vault.secret_values()
            self._secrets = (time.monotonic(), values)
        return values

    @staticmethod
    def _meta(row):
        return {k: row[k] for k in META_FIELDS} if row else None

    @staticmethod
    def _row(con, note_id):
        return con.execute("SELECT * FROM note_meta WHERE note_id=?", (note_id,)).fetchone()

    @staticmethod
    def _log(con, note_id, op, surface, client_id, summary, from_version=None, to_version=None,
             before=None, after=None, session=None):
        return con.execute("""INSERT INTO changes(ts,note_id,op,from_version,to_version,before_meta,after_meta,
                              surface,client_id,session,summary) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                           (now(), note_id, op, from_version, to_version,
                            json.dumps(before) if before else None, json.dumps(after) if after else None,
                            surface, client_id, session, summary[:300])).lastrowid

    @staticmethod
    def _write_meta(con, note_id, version, meta, origin=None):
        stamp = now()
        con.execute("""INSERT INTO note_meta(note_id,title,current_version,type,scope,sensitivity,status,pinned,
                       verified_at,review_by,supersedes,origin,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(note_id) DO UPDATE SET title=excluded.title,current_version=excluded.current_version,
                       type=excluded.type,scope=excluded.scope,sensitivity=excluded.sensitivity,status=excluded.status,
                       pinned=excluded.pinned,verified_at=excluded.verified_at,review_by=excluded.review_by,
                       supersedes=excluded.supersedes,updated_at=excluded.updated_at""",
                    (note_id, meta["title"], version, meta["type"], meta["scope"], meta["sensitivity"], meta["status"],
                     int(bool(meta["pinned"])), meta["verified_at"], meta["review_by"], meta["supersedes"], origin,
                     stamp, stamp))

    def _ensure_project(self, con, scope, cwd=None):
        if not scope.startswith("project:"):
            return
        key = scope[8:]
        row = con.execute("SELECT path_globs FROM projects WHERE key=?", (key,)).fetchone()
        glob = norm_path(cwd) + "/**" if cwd and norm_path(cwd) not in self.home_paths else None
        if row is None:
            stamp = now()
            con.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)",
                        (key, key, "", json.dumps([glob] if glob else []), "[]", json.dumps([key]), stamp, stamp))
        elif glob and glob not in json.loads(row["path_globs"]):
            con.execute("UPDATE projects SET path_globs=?,updated_at=? WHERE key=?",
                        (json.dumps(json.loads(row["path_globs"]) + [glob]), now(), key))

    @staticmethod
    def _receipt(meta, change_id, verb="saved"):
        return f"📝 {verb}: {meta['title']} · {meta['scope']} · {meta['type']} · undo #{change_id}"

    def _active_in_scope(self, scope):
        with self.store.connection() as con:
            return con.execute("SELECT * FROM note_meta WHERE scope=? AND status='active' ORDER BY updated_at DESC LIMIT 3000",
                               (scope,)).fetchall()

    def find_duplicates(self, title, content, scope, exclude=None):
        new_title, new_title_words, new_words = _norm_title(title), _words(title), _words(content)
        found = []
        for row in self._active_in_scope(scope):
            if row["note_id"] == exclude:
                continue
            same_title = bool(new_title) and _norm_title(row["title"]) == new_title
            title_score = _jaccard(new_title_words, _words(row["title"]))
            if not same_title and title_score < 0.3:
                # Cheap prefilter: only read bodies of notes whose titles overlap at all.
                body_score = 0.0
                if len(new_words) >= 8:
                    _, body = self.store.note_body(row["current_version"])
                    body_score = _jaccard(new_words, _words(body))
                if body_score < 0.5:
                    continue
            else:
                _, body = self.store.note_body(row["current_version"])
                body_score = _jaccard(new_words, _words(body))
            if same_title or title_score >= 0.6 or body_score >= 0.5:
                found.append({"note_id": row["note_id"], "version": row["current_version"], "title": row["title"],
                              "type": row["type"], "excerpt": body[:300], "score": round(max(title_score, body_score, float(same_title)), 2)})
        return sorted(found, key=lambda c: -c["score"])[:5]

    # ---------- writes ----------

    def remember(self, title, content, type, scope="global", note_id=None, expected_version=None, evidence_type=None,
                 sensitivity="normal", review_days=None, verified_at=None, supersedes=None, pinned=None,
                 force_new=False, cwd=None, surface="unknown", client_id=None, session=None, source_date=None,
                 source_reference=None, origin=None):
        if type not in TYPES:
            raise ValueError("type must be one of: " + ", ".join(TYPES))
        if sensitivity not in SENSITIVITY:
            raise ValueError("sensitivity must be 'normal' or 'private'")
        scope = check_scope(scope)
        exact = self._secret_values()
        title, title_hits = scrub(title.strip(), exact)
        content, content_hits = scrub(content.strip(), exact)
        redacted = sum(title_hits.values()) + sum(content_hits.values())
        evidence_type = evidence_type or ("preference" if type == "preference" else "project_update")
        verified = verified_at or now()
        days = review_days if review_days is not None else REVIEW_DAYS.get(type)
        review_by = (date.fromisoformat(verified[:10]) + timedelta(days=days)).isoformat() if days else None

        if note_id is None and not force_new:
            duplicates = self.find_duplicates(title, content, scope)
            if duplicates:
                return {"status": "possible_duplicate", "persisted": False, "candidates": duplicates,
                        "hint": "Revise one with remember(note_id=..., expected_version=...), or pass force_new=true if it is genuinely different."}

        new_id = None if note_id else uuid.uuid4().hex
        target = note_id or new_id
        outcome = {}

        def commit(con, version, previous):
            before_row = self._row(con, target)
            before = self._meta(before_row)
            meta = {"title": title, "type": type, "scope": scope, "sensitivity": sensitivity, "status": "active",
                    "pinned": bool(pinned) if pinned is not None else bool(before and before["pinned"]),
                    "verified_at": verified, "review_by": review_by,
                    "supersedes": supersedes if supersedes is not None else (before or {}).get("supersedes")}
            self._ensure_project(con, scope, cwd)
            self._write_meta(con, target, version, meta, origin or surface)
            op = "revise" if before_row else ("migrate" if "migration" in (surface, origin) else "create")
            outcome["change_id"] = self._log(con, target, op, surface, client_id, f"{op}: {title}", previous, version,
                                             before, meta, session)
            outcome["meta"] = meta
            if supersedes and supersedes != target:
                old = self._row(con, supersedes)
                if old and old["status"] == "active":
                    old_meta = self._meta(old)
                    con.execute("UPDATE note_meta SET status='archived',updated_at=? WHERE note_id=?", (now(), supersedes))
                    self._log(con, supersedes, "archive", surface, client_id, f"superseded by {title}", old["current_version"],
                              old["current_version"], old_meta, {**old_meta, "status": "archived"}, session)

        result = self.store.save_note(title, content, evidence_type, source_date, source_reference, note_id, expected_version,
                                      header_extra={"type": type, "scope": scope}, on_commit=commit, new_note_id=new_id)
        return {"status": "saved", "persisted": True, "note_id": target, "version": result["version"],
                "change_id": outcome["change_id"], "redacted": redacted,
                "receipt": self._receipt(outcome["meta"], outcome["change_id"], "revised" if note_id else "saved")}

    def _meta_update(self, note_id, op, changes, surface, client_id, summary, session=None, require=None):
        with self.store.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = self._row(con, note_id)
            if row is None:
                raise ValueError("Note not found")
            if require and not require(row):
                raise ValueError(f"Cannot {op} this note in its current state ({row['status']})")
            before = self._meta(row)
            after = {**before, **changes}
            sets = ",".join(f"{k}=?" for k in changes)
            con.execute(f"UPDATE note_meta SET {sets},updated_at=? WHERE note_id=?", (*changes.values(), now(), note_id))
            change_id = self._log(con, note_id, op, surface, client_id, f"{op}: {row['title']}{' · ' + summary if summary else ''}",
                                  row["current_version"], row["current_version"], before, after, session)
        verb = {"verify": "verified", "archive": "archived", "restore": "restored", "relabel": "relabelled"}.get(op, op)
        return {"note_id": note_id, "change_id": change_id, "receipt": self._receipt(after, change_id, verb)}

    def verify_note(self, note_id, surface="unknown", client_id=None, session=None):
        with self.store.connection() as con:
            row = self._row(con, note_id)
        if row is None:
            raise ValueError("Note not found")
        days = REVIEW_DAYS.get(row["type"])
        stamp = now()
        review_by = (_today() + timedelta(days=days)).isoformat() if days else None
        return self._meta_update(note_id, "verify", {"verified_at": stamp, "review_by": review_by}, surface, client_id, "", session)

    def archive_note(self, note_id, reason="", surface="unknown", client_id=None, session=None):
        return self._meta_update(note_id, "archive", {"status": "archived"}, surface, client_id, reason[:200], session,
                                 require=lambda r: r["status"] == "active")

    def restore_note(self, note_id, surface="unknown", client_id=None, session=None):
        return self._meta_update(note_id, "restore", {"status": "active"}, surface, client_id, "", session,
                                 require=lambda r: r["status"] == "archived")

    def set_meta(self, note_id, surface="unknown", client_id=None, session=None, **fields):
        """Change labels (pin, scope, type, sensitivity, review date) without rewriting the content."""
        allowed = {k: v for k, v in fields.items() if k in ("type", "scope", "sensitivity", "pinned", "review_by") and v is not None}
        if not allowed:
            raise ValueError("Nothing to change")
        if "type" in allowed and allowed["type"] not in TYPES:
            raise ValueError("Unknown type")
        if "scope" in allowed:
            allowed["scope"] = check_scope(allowed["scope"])
            with self.store.connection() as con:
                self._ensure_project(con, allowed["scope"])
        if "sensitivity" in allowed and allowed["sensitivity"] not in SENSITIVITY:
            raise ValueError("Unknown sensitivity")
        if "pinned" in allowed:
            allowed["pinned"] = int(bool(allowed["pinned"]))
        return self._meta_update(note_id, "relabel", allowed, surface, client_id, ", ".join(allowed), session)

    def delete_note(self, note_id, surface="unknown", client_id=None, reason=""):
        with self.store.connection() as con:
            row = self._row(con, note_id)
        result = self.store.delete_note(note_id)
        with self.store.connection() as con:
            self._log(con, note_id, "delete", surface, client_id, f"delete: {row['title'] if row else note_id}"
                      + (f" · {reason[:200]}" if reason else ""), row["current_version"] if row else None, None,
                      self._meta(row), None)
        return result

    def revert_change(self, change_id, surface="unknown", client_id=None, session=None, force=False):
        """Put the note back to its state just before `change_id`."""
        with self.store.connection() as con:
            change = con.execute("SELECT * FROM changes WHERE id=?", (change_id,)).fetchone()
            if change is None:
                raise ValueError("Change not found")
            if change["op"] == "delete":
                raise ValueError("A hard delete cannot be reverted")
            if change["reverted_by"]:
                raise ValueError(f"Change #{change_id} was already reverted by #{change['reverted_by']}")
            later = [r[0] for r in con.execute("SELECT id FROM changes WHERE note_id=? AND id>? AND op!='delete'",
                                                (change["note_id"], change_id))]
            row = self._row(con, change["note_id"])
        if re.fullmatch(r"[tpf]:\d+", change["note_id"]):
            if self.contacts is None:
                raise ValueError("Contacts are not enabled on this server")
            if later and not force:
                raise ValueError(f"Later changes exist ({', '.join('#' + str(i) for i in later)}); revert those first or pass force=true")
            return self.contacts.revert(change, surface, client_id, session)
        if row is None:
            raise ValueError("The note no longer exists")
        if later and not force:
            raise ValueError(f"Later changes exist ({', '.join('#' + str(i) for i in later)}); revert those first or pass force=true")
        before = json.loads(change["before_meta"]) if change["before_meta"] else None
        note_id = change["note_id"]
        if before is None:  # create/migrate: the note did not exist before, so archive it.
            target_meta, target_version = {**self._meta(row), "status": "archived"}, row["current_version"]
        else:
            target_meta, target_version = before, change["from_version"] or row["current_version"]
        outcome = {}

        def commit(con, version, previous):
            current = self._row(con, note_id)
            self._write_meta(con, note_id, version, target_meta)
            outcome["id"] = self._log(con, note_id, "revert", surface, client_id, f"revert #{change_id}: {target_meta['title']}",
                                      previous or current["current_version"], version, self._meta(current), target_meta, session)
            con.execute("UPDATE changes SET reverted_by=? WHERE id=?", (outcome["id"], change_id))

        if target_version != row["current_version"]:
            self.store.restore_version(note_id, target_version, row["current_version"],
                                       header_extra={"type": target_meta["type"], "scope": target_meta["scope"]}, on_commit=commit)
        else:
            with self.store.connection() as con:
                con.execute("BEGIN IMMEDIATE")
                commit(con, row["current_version"], row["current_version"])
        return {"reverted": change_id, "change_id": outcome["id"],
                "receipt": self._receipt(target_meta, outcome["id"], f"reverted #{change_id}")}

    # ---------- reads ----------

    def resolve_id(self, note_id):
        """Accept a full note id or the short prefix that boot and receipts show."""
        note_id = (note_id or "").strip().lower().removeprefix("notes/")
        if re.fullmatch(r"[a-f0-9]{32}", note_id):
            return note_id
        if not re.fullmatch(r"[a-f0-9]{6,31}", note_id):
            raise ValueError("note_id must be a note id or its first 6+ hex characters")
        with self.store.connection() as con:
            rows = con.execute("SELECT note_id FROM note_meta WHERE note_id LIKE ? LIMIT 3", (note_id + "%",)).fetchall()
        if len(rows) != 1:
            raise ValueError("No note matches that id" if not rows else "Ambiguous id prefix; use more characters")
        return rows[0][0]

    def get_note(self, note_id, trusted=True):
        with self.store.connection() as con:
            row = self._row(con, note_id)
            history = con.execute("SELECT * FROM changes WHERE note_id=? ORDER BY id DESC LIMIT 50", (note_id,)).fetchall()
        if row is None or (not trusted and row["sensitivity"] == "private"):
            raise ValueError("Note not found")
        header, content = self.store.note_body(row["current_version"])
        return {**dict(row), "evidence_type": header.get("evidence_type"), "source_date": header.get("source_date"),
                "source_reference": header.get("source_reference"), "content": content, "stale": self._stale(row),
                "history": [self._change(r) for r in history]}

    def version_text(self, note_id, document_id):
        with self.store.connection() as con:
            if not con.execute("SELECT 1 FROM revisions WHERE uri=? AND document_id=?", (f"notes/{note_id}", document_id)).fetchone():
                raise ValueError("Unknown version")
        return self.store.note_body(document_id)[1]

    def list_notes(self, type=None, scope=None, status="active", stale=None, q=None, limit=100, offset=0, trusted=True):
        clauses, params = [], []
        for col, val in (("type", type), ("scope", scope), ("status", status)):
            if val:
                clauses.append(f"{col}=?")
                params.append(val)
        if not trusted:
            clauses.append("sensitivity!='private'")
        if stale:
            clauses.append("review_by IS NOT NULL AND review_by<? AND pinned=0 AND status='active'")
            params.append(_today().isoformat())
        if q:
            clauses.append("title LIKE ? ESCAPE '\\'")
            params.append("%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.store.connection() as con:
            total = con.execute("SELECT count(*) FROM note_meta" + where, params).fetchone()[0]
            rows = con.execute("SELECT * FROM note_meta" + where + " ORDER BY pinned DESC,updated_at DESC LIMIT ? OFFSET ?",
                               params + [min(max(limit, 1), 500), max(offset, 0)]).fetchall()
        return {"total": total, "notes": [{**dict(r), "stale": self._stale(r)} for r in rows]}

    @staticmethod
    def _change(r):
        item = dict(r)
        for k in ("before_meta", "after_meta"):
            item[k] = json.loads(item[k]) if item[k] else None
        return item

    def list_changes(self, since=None, limit=50, note_id=None, trusted=True):
        clauses, params = [], []
        if since:
            clauses.append("c.ts>=?")
            params.append(since)
        if note_id:
            clauses.append("c.note_id=?")
            params.append(note_id)
        if not trusted:
            clauses.append("coalesce(m.sensitivity,'normal')!='private' AND coalesce(t.sensitivity,ft.sensitivity,'normal')!='private'"
                           " AND coalesce(p.sensitivity,'normal')!='private'")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        joins = (" LEFT JOIN note_meta m ON m.note_id=c.note_id LEFT JOIN threads t ON c.note_id='t:'||t.id"
                 " LEFT JOIN follows f ON c.note_id='f:'||f.id LEFT JOIN threads ft ON ft.id=f.thread_id"
                 " LEFT JOIN people p ON c.note_id='p:'||p.id")
        with self.store.connection() as con:
            rows = con.execute("SELECT c.* FROM changes c" + joins + where +
                               " ORDER BY c.id DESC LIMIT ?", params + [min(max(limit, 1), 500)]).fetchall()
        return {"changes": [self._change(r) for r in rows]}

    # ---------- projects ----------

    def set_project(self, key, title=None, summary=None, path_globs=None, git_remotes=None, aliases=None):
        if not PROJECT_KEY.fullmatch(key or ""):
            raise ValueError("Project key: lowercase letters, digits, . _ - (max 64)")
        with self.store.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM projects WHERE key=?", (key,)).fetchone()
            stamp = now()
            cur = dict(row) if row else {"title": key, "summary": "", "path_globs": "[]", "git_remotes": "[]",
                                         "aliases": json.dumps([key]), "created_at": stamp}
            values = (key, title if title is not None else cur["title"], summary if summary is not None else cur["summary"],
                      json.dumps(sorted({norm_path(g) for g in path_globs})) if path_globs is not None else cur["path_globs"],
                      json.dumps(sorted({norm_remote(r) for r in git_remotes})) if git_remotes is not None else cur["git_remotes"],
                      json.dumps(sorted({a.lower() for a in aliases})) if aliases is not None else cur["aliases"],
                      cur["created_at"], stamp)
            con.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?,?,?,?,?,?)", values)
        return self.get_project(key)

    def get_project(self, key):
        with self.store.connection() as con:
            row = con.execute("SELECT * FROM projects WHERE key=?", (key,)).fetchone()
            count = con.execute("SELECT count(*) FROM note_meta WHERE scope=? AND status='active'", ("project:" + key,)).fetchone()[0]
        if row is None:
            raise ValueError("Unknown project")
        return {**{k: (json.loads(row[k]) if k in ("path_globs", "git_remotes", "aliases") else row[k]) for k in row.keys()},
                "active_notes": count}

    def list_projects(self):
        with self.store.connection() as con:
            rows = con.execute("""SELECT p.*,(SELECT count(*) FROM note_meta m WHERE m.scope='project:'||p.key AND m.status='active') AS active_notes
                                  FROM projects p ORDER BY p.key""").fetchall()
        return {"projects": [{**dict(r), **{k: json.loads(r[k]) for k in ("path_globs", "git_remotes", "aliases")}} for r in rows]}

    def resolve_project(self, cwd=None, git_remote=None, project=None):
        projects = self.list_projects()["projects"]
        if project:
            key = project.removeprefix("project:").lower()
            return next((p for p in projects if p["key"] == key or key in p["aliases"]), None)
        path = norm_path(cwd)
        if path and path not in self.home_paths:
            best, best_len = None, -1
            for p in projects:
                for glob in p["path_globs"]:
                    base = glob.removesuffix("/**")
                    if (path == base or fnmatch(path, glob) or path.startswith(base + "/")) and len(base) > best_len:
                        best, best_len = p, len(base)
            if best:
                return best
        remote = norm_remote(git_remote)
        if remote:
            for p in projects:
                if remote in p["git_remotes"]:
                    return p
        if path and path not in self.home_paths:
            name = path.rsplit("/", 1)[-1]
            for p in projects:
                if name == p["key"] or name in p["aliases"]:
                    return p
        return None

    # ---------- boot ----------

    @staticmethod
    def _stale(row):
        # Pinned notes are Bash's curated canon; they are revised, not re-verified.
        return (bool(row["review_by"]) and row["review_by"] < _today().isoformat() and row["status"] == "active"
                and not row["pinned"])

    def _render(self, row, body_limit):
        _, body = self.store.note_body(row["current_version"])
        flag = f" ⚠ UNVERIFIED since {(row['verified_at'] or row['created_at'])[:10]}, verify before acting" if self._stale(row) else ""
        if len(body) > body_limit:
            body = body[:body_limit].rsplit("\n", 1)[0] + f"\n… (truncated; read_note {row['note_id']})"
        return f"### {row['title']} [{row['type']} · {row['note_id'][:8]}]{flag}\n{body}\n"

    @staticmethod
    def _line(row, stale):
        flag = " ⚠ UNVERIFIED" if stale else ""
        return f"- {row['title']} [{row['type']} · {row['scope']} · {row['note_id'][:8]}]{flag}"

    def _fill(self, rows, body_limit, budget):
        """Render notes in full while `budget` lasts, then as one-line entries."""
        out, used = [], 0
        for r in rows:
            text = self._render(r, body_limit)
            if used + len(text) > budget:
                text = self._line(r, self._stale(r))
            out.append(text)
            used += len(text) + 1
        return out

    @staticmethod
    def _fit(parts, limit=PART_LIMIT):
        out, used, dropped = [], 0, 0
        for text in parts:
            if used + len(text) + 1 > limit:
                dropped += 1
                continue
            out.append(text)
            used += len(text) + 1
        if dropped:
            note = f"\n(+{dropped} more not shown; use search_memory / list_notes)"
            while out and used + len(note) > limit:
                used -= len(out.pop()) + 1
            out.append(note)
        return "\n".join(out)

    def _notes(self, where, params=()):
        with self.store.connection() as con:
            return con.execute("SELECT * FROM note_meta WHERE status='active' AND sensitivity!='private' AND " + where,
                               params).fetchall()

    PROTOCOL = ("Memory protocol (watchthelight, Bash's long-term memory):\n"
                "- This boot context is current notes, not archive text. Search with search_memory before asking Bash anything you might already know.\n"
                "- Save durable facts without asking via remember: decisions, fixes, gotchas, config/infra changes, preferences, status changes, open loops. Never secrets.\n"
                "- On possible_duplicate, revise the matching note instead of creating a new one.\n"
                "- Echo every receipt line verbatim so Bash sees each write.\n"
                "- ⚠ UNVERIFIED facts may be stale: check live before acting, then verify_note. Close finished loops with archive_note.\n")

    def boot(self, part="all", cwd=None, git_remote=None, project=None, surface=None, include_infra=True):
        if part == "all":
            return "\n\n".join(self.boot(p, cwd, git_remote, project, surface, include_infra) for p in PARTS)
        if part not in PARTS:
            raise ValueError("part must be one of: all, " + ", ".join(PARTS))
        stamp = _today().isoformat()
        if part == "profile":
            pinned = self._notes("scope='global' AND pinned=1 ORDER BY updated_at DESC")
            prefs = self._notes("scope='global' AND pinned=0 AND type='preference' ORDER BY updated_at DESC")
            other = self._notes("scope='global' AND pinned=0 AND type NOT IN ('preference','session_digest','open_loop') ORDER BY updated_at DESC")
            blocks = [f"# watchthelight boot · profile · {stamp}\n{self.PROTOCOL}", "## Pinned"]
            blocks += self._fill(pinned, 2500, PART_LIMIT - 3500) or ["(none pinned)"]
            blocks.append("## Preferences")
            used = sum(len(b) + 1 for b in blocks)
            blocks += self._fill(prefs, 700, PART_LIMIT - 1500 - used) or ["(none yet)"]
            if other:
                blocks.append("## Other global facts (read_note for detail)")
                blocks += [self._line(r, self._stale(r)) for r in other]
            return self._fit(blocks)
        if part == "infra":
            runbooks = self._notes("type='runbook' ORDER BY scope,title")
            blocks = [f"# watchthelight boot · infra · {stamp}", "## Runbooks (read_note or search 'RUNBOOK <name>' for detail)"]
            for r in runbooks:
                _, body = self.store.note_body(r["current_version"])
                first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")[:220]
                blocks.append(self._line(r, self._stale(r)) + (f": {first}" if first else ""))
            if len(blocks) == 2:
                blocks.append("(no runbooks yet)")
            if include_infra and self.vault is not None:
                blocks.append("## Vault services by project (names only; list_credentials → get_credential with a reason)")
                groups = {}
                for c in self.vault.list(limit=1000)["credentials"]:
                    if {"third-party", "do-not-use"} & set(c["tags"]):
                        continue
                    groups.setdefault(c["project"] or "(none)", set()).add(c["service"])
                for proj in sorted(groups, key=lambda p: (p == "browser-passwords", p)):
                    names = sorted(groups[proj])
                    shown = ", ".join(names[:12]) + (f" (+{len(names) - 12})" if len(names) > 12 else "")
                    blocks.append(f"- {proj}: {shown}")
            return self._fit(blocks)
        if part == "project":
            match = self.resolve_project(cwd, git_remote, project)
            head = f"# watchthelight boot · project · {stamp}"
            if match is None:
                where = f" `{cwd}`" if cwd else ""
                return (f"{head}\nNo project registered for this folder{where}. If work here becomes a project, the first "
                        f"remember(..., scope='project:<key>', cwd=<this folder>) registers it. Global notes still apply.")
            notes = self._notes("scope=? ORDER BY CASE type WHEN 'runbook' THEN 0 WHEN 'gotcha' THEN 1 WHEN 'decision' THEN 2 "
                                "WHEN 'open_loop' THEN 3 WHEN 'fact' THEN 4 WHEN 'preference' THEN 5 ELSE 6 END, updated_at DESC",
                                ("project:" + match["key"],))
            cutoff = (_today() - timedelta(days=DIGEST_BOOT_DAYS)).isoformat()
            notes = [n for n in notes if n["type"] != "session_digest" or n["updated_at"][:10] >= cutoff]
            blocks = [head, f"## {match['title']} (project:{match['key']})" + (f"\n{match['summary']}" if match["summary"] else "")]
            body_budget = PART_LIMIT - 1200
            used = sum(len(b) for b in blocks)
            index = []
            for n in notes:
                text = self._render(n, 2500)
                if used + len(text) < body_budget:
                    blocks.append(text)
                    used += len(text)
                else:
                    index.append(self._line(n, self._stale(n)))
            if index:
                blocks.append("## More notes in this project")
                blocks += index
            if not notes:
                blocks.append("(no notes yet for this project)")
            return self._fit(blocks)
        if part == "people":
            if self.contacts is None:
                return f"# watchthelight boot · people · {stamp}\n(contacts are not enabled on this server)"
            return self.contacts.boot_part(stamp, self._fit)
        # threads
        loops = self._notes("type='open_loop' ORDER BY updated_at DESC")
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with self.store.connection() as con:
            recent = con.execute("""SELECT c.note_id,max(c.ts) AS ts,group_concat(DISTINCT c.op) AS ops,m.title,m.scope,m.type
                                    FROM changes c JOIN note_meta m ON m.note_id=c.note_id
                                    WHERE c.ts>=? AND c.op!='migrate' AND m.sensitivity!='private'
                                    GROUP BY c.note_id ORDER BY ts DESC LIMIT 60""",
                                 (since,)).fetchall()
        projects = self.list_projects()["projects"]
        blocks = [f"# watchthelight boot · threads · {stamp}"]
        line = self.contacts.summary_line() if self.contacts is not None else None
        if line:
            blocks.append(line)  # second, so _fit never drops it
        blocks.append("## Open loops")
        blocks += [self._line(r, self._stale(r)) for r in loops] or ["(none)"]
        blocks.append("## Changed in the last 7 days")
        blocks += [f"- {r['ts'][:10]} {r['ops']}: {r['title']} [{r['type']} · {r['scope']} · {r['note_id'][:8]}]" for r in recent] or ["(nothing)"]
        blocks.append("## Projects")
        blocks += ["- " + " · ".join(x for x in (p["key"], p["title"] if p["title"] != p["key"] else "",
                                                   p["summary"][:120], f"{p['active_notes']} notes") if x)
                   for p in projects] or ["(none registered)"]
        return self._fit(blocks)
