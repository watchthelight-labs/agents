from concurrent.futures import ThreadPoolExecutor
import io

import pytest
from starlette.testclient import TestClient

from memory_mcp.cli import import_directory
from memory_mcp.server import create_app
from memory_mcp.store import Store, passage_chunks


TOKEN = "test-only-" + "x" * 48


def test_streaming_offsets_and_boundaries():
    source = ("A long line with unicode: 日本語 café.\r\n" * 700) + "the last line"
    passages = list(passage_chunks(io.StringIO(source)))
    assert len(passages) > 3
    for start, end, text in passages:
        assert source[start:end] == text
        assert len(text) <= 6000
    assert passages[0][0] == 0
    assert passages[-1][1] == len(source)
    assert all(a[1] >= b[0] for a, b in zip(passages, passages[1:]))


def test_incremental_import_dedup_revision_and_citations(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    original = "Shatterfish is paused as of September 26.\n" * 200
    first = root / "first.txt"
    first.write_text(original, encoding="utf-8", newline="")
    (root / "duplicate.txt").write_text(original, encoding="utf-8", newline="")
    store = Store(tmp_path / "db")
    assert import_directory(store, root, "inbox") == 0
    assert store.status()["unique_documents"] == 1
    before = store.status()["passages"]
    assert import_directory(store, root, "inbox") == 0
    assert store.status()["recent_imports"][0]["changed"] == 0
    assert store.status()["passages"] == before
    result = store.search("Shatterfish paused")["results"][0]
    passage = store.read(result["document_id"], result["ordinal"], 1)["passages"][0]
    assert passage["text"] == original[passage["start_char"]:passage["end_char"]]
    assert store.search('" OR * --')["results"] == []
    assert len(store.search("Shatterfish")["results"]) == len({r["ordinal"] for r in store.search("Shatterfish")["results"]})
    assert not store.search("Shatterfish", source_prefix="inbox/%")["results"]


def test_note_revision_is_atomic_and_old_state_stops_matching(tmp_path):
    store = Store(tmp_path / "db")
    note = store.save_note("Project state", "Previously stalled llama", "project_update", "2026-10-13")
    def update(word):
        try:
            return store.save_note("Project state", word, "project_update", note_id=note["note_id"], expected_version=note["version"])
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, ["Currently running zebra", "Currently testing otter"]))
    assert sum(r is not None for r in outcomes) == 1
    assert store.search("llama")["results"] == []
    assert store.read(note["version"])["historical_revision_only"] is True
    assert store.status()["sources"] == 1
    with pytest.raises(ValueError):
        store.save_note("bad", "bad", "confirmed_by_ai")
    with pytest.raises(ValueError):
        store.read("../../secret")


def test_bad_utf8_never_publishes_partial_document(tmp_path):
    store = Store(tmp_path / "db")
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"valid " * 4000 + b"\xff")
    with pytest.raises(UnicodeError):
        store.ingest(bad, "inbox/bad.txt")
    assert store.status()["sources"] == 0
    assert store.status()["unique_documents"] == 0


def test_auth_protocol_tools_and_host_boundary(tmp_path):
    app = create_app(tmp_path / "db", TOKEN)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        for method, path in [("POST", "/mcp"), ("GET", "/mcp"), ("GET", "/")]:
            assert client.request(method, path).status_code == 401
        assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401
        headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json, text/event-stream"}
        initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "acceptance", "version": "1"}}}
        response = client.post("/mcp", json=initialize, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["serverInfo"]["name"] == "watchthelight"
        assert "call boot first" in response.json()["result"]["instructions"]
        headers["MCP-Protocol-Version"] = response.json()["result"]["protocolVersion"]
        listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, headers=headers)
        names = {t["name"] for t in listed.json()["result"]["tools"]}
        assert names == {"boot", "search_memory", "read_source", "list_sources", "read_note", "list_notes", "remember",
                         "verify_note", "archive_note", "restore_note", "relabel_note", "list_changes", "revert_change",
                         "list_projects", "set_project", "memory_status", "delete_note", "forget_source",
                         "log_contact", "list_threads", "inbox", "mark_seen", "follow", "set_person"}
        assert len(names) <= 30  # every tool description costs context in every client
        call = {"name": "remember", "arguments": {"title": "Chart colours", "content": "Sage green charts on black", "type": "preference"}}
        saved = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": call}, headers=headers)
        assert saved.status_code == 200
        result = saved.json()["result"]
        assert not result.get("isError"), result
        assert "📝 saved: Chart colours" in result["content"][0]["text"]
        assert Store(tmp_path / "db").search("sage")["results"]
        bad = {"name": "read_note", "arguments": {"note_id": "zz"}}
        failed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": bad}, headers=headers).json()["result"]
        assert failed["isError"] and "6+ hex characters" in failed["content"][0]["text"]
        prompts = client.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}, headers=headers)
        assert [p["name"] for p in prompts.json()["result"]["prompts"]] == ["boot"]
        assert client.get("/boot?part=profile").status_code == 401
        booted = client.get("/boot?part=profile", headers={"Authorization": "Bearer " + TOKEN})
        assert booted.status_code == 200 and "Sage green charts" in booted.text
        assert client.get("/boot?part=nope", headers={"Authorization": "Bearer " + TOKEN}).status_code == 400
        assert client.post("/mcp", json=initialize, headers={**headers, "Origin": "https://untrusted.example"}).status_code == 403
        assert client.post("/mcp", json=initialize, headers={**headers, "Host": "untrusted.example"}).status_code == 421
    with pytest.raises(ValueError):
        create_app(tmp_path / "db2", "short")
