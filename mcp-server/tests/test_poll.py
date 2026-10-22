from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlsplit

from memory_mcp.contacts import Contacts
from memory_mcp.github_poll import GitHub, Poller, Response
from memory_mcp.memory import Memory
from memory_mcp.store import Store


class FakeGitHub:
    """Routes by URL path; each route is a list of responses served in order (the last one repeats)."""

    def __init__(self):
        self.routes, self.calls = {}, []

    def add(self, path, *responses):
        self.routes.setdefault(path, []).extend(responses)

    def __call__(self, url, headers):
        parts = urlsplit(url)
        self.calls.append((parts.path, parts.query, headers.get("If-None-Match")))
        queue = self.routes.get(parts.path)
        if not queue:
            return Response(404, '{"message":"Not Found"}', {"X-RateLimit-Remaining": "4999"})
        status, body, headers_out = queue.pop(0) if len(queue) > 1 else queue[0]
        return Response(status, json.dumps(body) if body is not None else "",
                        {"X-RateLimit-Remaining": "4999", **(headers_out or {})})


def issue(number=1, state="open", updated="2026-10-22T12:00:00Z", user="alice", pr=False, merged=None, title="A bug"):
    d = {"number": number, "state": state, "updated_at": updated, "created_at": "2026-10-01T00:00:00Z", "title": title,
         "user": {"login": user, "type": "User"}, "body": "the report", "locked": False,
         "html_url": f"https://github.com/o/r/{'pull' if pr else 'issues'}/{number}"}
    if pr:
        d["pull_request"] = {"merged_at": merged}
    return d


def comment(cid, user, created, body="hello", bot=False):
    return {"id": cid, "user": {"login": user, "type": "Bot" if bot else "User"}, "created_at": created, "body": body,
            "html_url": f"https://github.com/o/r/issues/1#issuecomment-{cid}"}


def setup(tmp_path):
    store = Store(tmp_path / "db")
    memory = Memory(store)
    contacts = Contacts(store, memory)
    fake = FakeGitHub()
    return store, memory, contacts, fake


def run(contacts, fake, **kw):
    gh = GitHub("token", transport=fake, pause=0, sleep=lambda s: None, budget=kw.pop("budget", 400))
    return Poller(contacts, gh, ("watchthelight",), **kw).run()


def due_now(store):
    with store.connection() as con:
        con.execute("UPDATE follows SET next_check='2000-01-01'")


def test_baseline_then_reply_then_304(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    t = c.log_contact(url="https://github.com/o/r/issues/1#issuecomment-5", why="help", summary="our answer", surface="test")
    with store.connection() as con:  # pretend the follow existed before the conversation started
        con.execute("UPDATE follows SET baseline_before='2026-10-10T00:00:00Z'")
    fake.add("/repos/o/r/issues/1", (200, issue(updated="2026-10-22T12:00:00Z"), {"ETag": '"e1"'}),
             (304, None, {}))
    fake.add("/repos/o/r/issues/1/comments", (200, [comment(4, "alice", "2026-10-05T00:00:00Z"),
                                                    comment(5, "watchthelight", "2026-10-20T00:00:00Z"),
                                                    comment(6, "dependabot[bot]", "2026-10-21T00:00:00Z", bot=True),
                                                    comment(7, "alice", "2026-10-21T09:00:00Z", "thanks, trying it")], {}))
    out = run(c, fake)
    assert out["new_events"] == 1 and not out["errors"]
    box = c.inbox()
    assert [u["author"] for u in box["unread"]] == ["alice"] and box["unread"][0]["excerpt"] == "thanks, trying it"
    thread = c.list_threads(t["thread_id"])
    assert thread["thread"]["state"] == "waiting_on_us" and thread["thread"]["title"] == "A bug"
    ours = [i for i in thread["interactions"] if i["direction"] == "out"]
    assert len(ours) == 1 and ours[0]["summary"] == "our answer"   # poller merged into the logged comment
    due_now(store)
    out = run(c, fake)
    assert out["not_modified"] == 1 and out["new_events"] == 0
    assert fake.calls[-1][2] == '"e1"'
    assert "o/r#1" in memory.boot("people") and "thanks" not in memory.boot("people")


def test_seeded_history_is_seen_and_states_follow_events(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    t = c.log_contact(url="https://github.com/o/r/issues/1", why="report", surface="test")
    fake.add("/repos/o/r/issues/1", (200, issue(updated="2026-10-21T00:00:00Z"), {}),
             (200, issue(state="closed", updated="2026-10-22T00:00:00Z"), {}))
    fake.add("/repos/o/r/issues/1/comments", (200, [comment(1, "alice", "2026-10-02T00:00:00Z")], {}), (200, [], {}))
    assert run(c, fake)["new_events"] == 0          # everything before the follow existed counts as seen
    due_now(store)
    with store.connection() as con:
        con.execute("UPDATE threads SET state='open'")
    run(c, fake)
    row = c.list_threads(t["thread_id"])["thread"]
    assert row["remote_state"] == "closed" and row["state"] == "closed"


def test_pr_reviews_merge_and_repo_move(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    c.follow("o/r#9", surface="test")
    moved = issue(9, pr=True, merged="2026-10-22T00:00:00Z", updated="2026-10-22T00:00:00Z")
    moved["html_url"] = "https://github.com/neworg/r/pull/9"
    fake.add("/repos/o/r/issues/9", (200, moved, {}))
    fake.add("/repos/o/r/issues/9/comments", (200, [], {}))
    fake.add("/repos/o/r/pulls/9/comments", (200, [], {}))
    fake.add("/repos/o/r/pulls/9/reviews", (200, [{"id": 3, "user": {"login": "maint", "type": "User"}, "state": "APPROVED",
                                                    "body": "", "submitted_at": "2026-10-21T00:00:00Z",
                                                    "html_url": "https://github.com/o/r/pull/9#pullrequestreview-3"}], {}))
    run(c, fake)
    with store.connection() as con:
        f = con.execute("SELECT * FROM follows").fetchone()
        t = con.execute("SELECT * FROM threads").fetchone()
    assert f["target"] == "neworg/r#9" and f["kind"] == "pr"
    assert t["remote_state"] == "merged" and t["repo"] == "neworg/r"


def test_404s_deactivate_and_errors_back_off(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    c.follow("o/r#5", surface="test")
    for _ in range(3):
        due_now(store)
        run(c, fake)
    with store.connection() as con:
        assert con.execute("SELECT active,fail_count FROM follows").fetchone()[:] == (0, 3)
    c.follow("o/r#6", surface="test")
    fake.add("/repos/o/r/issues/6", (500, {"message": "boom"}, {}))
    out = run(c, fake)
    assert out["errors"]
    with store.connection() as con:
        f = con.execute("SELECT * FROM follows WHERE target='o/r#6'").fetchone()
    assert f["fail_count"] == 1 and f["next_check"] > f["updated_at"]


def test_rate_limit_pauses_and_budget_stops(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    for n in (1, 2, 3):
        c.follow(f"o/r#{n}", surface="test")
    fake.add("/repos/o/r/issues/1", (403, {"message": "rate"}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "4102444800"}))
    out = run(c, fake)
    assert out["paused_until"].startswith("2100")
    again = run(c, fake)
    assert again == {"paused_until": out["paused_until"]}
    store2, memory2, c2, fake2 = setup(tmp_path / "b")
    for n in (1, 2, 3):
        c2.follow(f"o/r#{n}", surface="test")
    out = run(c2, fake2, budget=2)
    assert out["requests"] == 2 and any("budget" in e for e in out["errors"])


def test_search_creates_unlogged_threads_and_releases(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    c.follow("involves:watchthelight -org:watchthelight-labs", kind="search", surface="test")
    c.follow("openwrt/mt76", surface="test")
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = "2020-01-01T00:00:00Z"
    fake.add("/search/issues", (200, {"items": [{"html_url": "https://github.com/x/y/issues/4", "title": "Elsewhere", "updated_at": recent},
                                                 {"html_url": "https://github.com/x/y/issues/1", "title": "Ancient", "updated_at": old}]}, {}))
    fake.add("/repos/openwrt/mt76/releases", (200, [{"id": 1, "tag_name": "v1", "name": "one", "draft": False,
                                                     "published_at": "2026-10-01T00:00:00Z", "author": {"login": "nbd"},
                                                     "html_url": "https://github.com/openwrt/mt76/releases/tag/v1"}], {}),
             (200, [{"id": 2, "tag_name": "v2", "name": "two", "draft": False, "published_at": "2099-01-01T00:00:00Z",
                     "author": {"login": "nbd"}, "html_url": "https://github.com/openwrt/mt76/releases/tag/v2"}], {}))
    run(c, fake)
    box = c.inbox(include_releases=True)
    assert [t["title"] for t in box["unlogged"]] == ["Elsewhere"] and box["releases"] == []
    with store.connection() as con:  # a search that found nothing yet must not move its cursor
        assert con.execute("SELECT cursor FROM follows WHERE kind='search'").fetchone()[0] is not None
    with store.connection() as con:
        assert con.execute("SELECT count(*) FROM follows WHERE target='x/y#4'").fetchone()[0] == 1
    due_now(store)
    run(c, fake)
    assert [r["summary"] for r in c.inbox(include_releases=True)["releases"]] == ["openwrt/mt76 v2: two"]


def test_poller_health_shows_in_boot(tmp_path):
    store, memory, c, fake = setup(tmp_path)
    c.follow("o/r#1", surface="test")
    assert "has not completed a run" in memory.boot("people")
    fake.add("/repos/o/r/issues/1", (200, issue(), {}))
    fake.add("/repos/o/r/issues/1/comments", (200, [], {}))
    run(c, fake)
    assert "⚠" not in memory.boot("people")
