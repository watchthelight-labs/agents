import json
import sqlite3

from cryptography.exceptions import InvalidTag
import pytest
from starlette.testclient import TestClient

from memory_mcp.cli import front_matter, import_directory
from memory_mcp.redact import scrub
from memory_mcp.server import create_app
from memory_mcp.store import Store
from memory_mcp.vault import Vault, new_key

TOKEN = "test-only-" + "x" * 48
SECRET = "Zq9-vault-secret-value-7781"


def make_vault(tmp_path, key=None):
    return Vault(tmp_path / "db", key or new_key())


def test_vault_roundtrip_names_only_and_audit(tmp_path):
    vault = make_vault(tmp_path)
    saved = vault.put("Cloudflare", {"Email": "a@b.c", "Global API Key": SECRET}, "Global", "stellarsite")
    assert saved["created"] and saved["secret_fields"] == ["Global API Key"]
    listed = vault.list("cloudflare")
    assert SECRET not in json.dumps(listed) and listed["credentials"][0]["fields"] == ["Email", "Global API Key"]
    raw = (tmp_path / "db" / "vault.sqlite3").read_bytes()
    assert SECRET.encode() not in raw
    with pytest.raises(ValueError):
        vault.get("Cloudflare", reason=" ")
    got = vault.get("Cloudflare", ["Global API Key"], "deploy dns", "claude-code")
    assert got["values"] == {"Global API Key": SECRET}
    event = vault.audit()["events"][0]
    assert (event["action"], event["client_id"], event["reason"], event["fields"]) == ("get", "claude-code", "deploy dns", ["Global API Key"])
    assert vault.secret_values() == {SECRET: "Cloudflare"}


def test_vault_wrong_key_and_row_swap_fail(tmp_path):
    key = new_key()
    vault = make_vault(tmp_path, key)
    a = vault.put("A", {"password": "aaaaaaaaaa"})
    b = vault.put("B", {"password": "bbbbbbbbbb"})
    with pytest.raises(InvalidTag):
        make_vault(tmp_path).get(a["id"], reason="test")
    with sqlite3.connect(tmp_path / "db" / "vault.sqlite3") as con:
        nonce, ct = con.execute("SELECT nonce,ciphertext FROM credentials WHERE id=?", (b["id"],)).fetchone()
        con.execute("UPDATE credentials SET nonce=?,ciphertext=? WHERE id=?", (nonce, ct, a["id"]))
    with pytest.raises(InvalidTag):
        vault.get(a["id"], reason="test")
    with pytest.raises(ValueError):
        Vault(tmp_path / "db2", "short")


def test_vault_versioning_ambiguity_and_delete(tmp_path):
    vault = make_vault(tmp_path)
    one = vault.put("AWS", {"Secret Access Key": "s" * 20}, "iam", "p1")
    vault.put("AWS", {"Secret Access Key": "t" * 20}, "iam", "p2")
    with pytest.raises(ValueError, match="already exists"):
        vault.put("AWS", {"x": "y"}, "iam", "p1")
    with pytest.raises(ValueError, match="Ambiguous"):
        vault.get("AWS", reason="test")
    assert vault.get("AWS", reason="test", project="p2")["values"]["Secret Access Key"] == "t" * 20
    with pytest.raises(ValueError, match="conflict"):
        vault.put("AWS", {"x": "y"}, "iam", "p1", cred_id=one["id"], expected_version="stale")
    updated = vault.put("AWS", {"x": "y"}, "iam", "p1", cred_id=one["id"], expected_version=one["version"])
    assert vault.put("AWS", {"z": "w"}, "iam", "p1", upsert=True)["id"] == one["id"]
    with pytest.raises(ValueError, match="conflict"):
        vault.delete(one["id"], updated["version"])
    current = vault.list(project="p1")["credentials"][0]["version"]
    assert vault.delete(one["id"], current)["deleted"] == one["id"]
    assert vault.count() == 1


def test_forget_erases_fts_history_and_orphans_but_keeps_shared(tmp_path):
    store = Store(tmp_path / "db")
    root = tmp_path / "inbox"
    root.mkdir()
    (root / "a.txt").write_text("platypus shared text", encoding="utf-8")
    (root / "b.txt").write_text("platypus shared text", encoding="utf-8")
    (root / "c.txt").write_text("wombat alone", encoding="utf-8")
    assert import_directory(store, root, "inbox") == 0
    shared = store.forget("inbox/a.txt")
    assert shared["documents_kept_shared"] == 1 and store.search("platypus")["results"]
    alone = store.search("wombat")["results"][0]["document_id"]
    assert store.forget("inbox/c.txt")["documents_erased"] == 1
    assert store.search("wombat")["results"] == []
    assert not list((tmp_path / "db" / "originals").rglob(alone + ".txt"))
    with pytest.raises(ValueError):
        store.read(alone)
    # The import timer must not resurrect an unchanged forgotten file, but a changed one returns.
    import_directory(store, root, "inbox")
    assert store.search("wombat")["results"] == []
    (root / "c.txt").write_text("wombat changed", encoding="utf-8")
    import_directory(store, root, "inbox")
    assert store.search("wombat changed")["results"]
    note = store.save_note("t", "echidna one", "self_report")
    store.save_note("t", "echidna two", "self_report", note_id=note["note_id"], expected_version=note["version"])
    assert store.delete_note(note["note_id"])["documents_erased"] == 2
    assert store.search("echidna")["results"] == [] and store.list_sources("notes/")["sources"] == []
    with sqlite3.connect(tmp_path / "db" / "memory.sqlite3") as con:
        con.execute("INSERT INTO passages(passages,rank) VALUES ('integrity-check',1)")


def test_search_modes_filters_and_listing(tmp_path):
    store = Store(tmp_path / "db")
    store.save_note("n1", "deployment pipeline alpha", "project_update", "2026-01-05")
    store.save_note("n2", "beta gamma", "project_update", "2026-09-01")
    assert store.search("alpha beta")["results"] == []
    assert len(store.search("alpha beta", mode="any")["results"]) == 2
    assert store.search("deploy")["results"] == []
    assert store.search("deploy", prefix=True)["results"]
    assert store.search('deploy" OR *', prefix=True, mode="any")["results"]
    assert len(store.search("alpha beta", mode="any", since="2026-06-01")["results"]) == 1
    assert len(store.search("alpha beta", mode="any", kind=["note", "curated"], until="2026-02-01")["results"]) == 1
    page = store.list_sources(limit=1)
    assert len(page["sources"]) == 1 and page["next_cursor"]
    assert len(store.list_sources(cursor=page["next_cursor"])["sources"]) == 1
    status = store.status()
    assert status["schema_version"] == 3 and status["ingestion_complete"] is True


def test_inbox_scrub_front_matter_and_vault_values(tmp_path, monkeypatch):
    store = Store(tmp_path / "db")
    vault = Vault(tmp_path / "db", new_key())
    vault.put("Supabase", {"DB Password": SECRET})
    root = tmp_path / "inbox"
    root.mkdir()
    (root / "leak.md").write_text("---\nkind: curated\nsource_date: 2026-10-01\n---\nhere it is " + SECRET +
                                  "\npassword = hunter2hunter2\nkey AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8")
    assert front_matter(root / "leak.md") == {"kind": "curated", "source_date": "2026-10-01"}
    assert import_directory(store, root, "inbox", vault) == 0
    hit = store.search("here it is")["results"][0]
    assert hit["kind"] == "curated" and hit["source_date"] == "2026-10-01"
    text = store.read(hit["document_id"])["passages"][0]["text"]
    assert SECRET not in text and "[REDACTED:vault:Supabase]" in text
    assert "hunter2hunter2" not in text and "AKIAABCDEFGHIJKLMNOP" not in text
    assert scrub("plain words")[0] == "plain words"


def test_vault_tools_over_mcp(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_VAULT_KEY", new_key())
    app = create_app(tmp_path / "db", TOKEN)
    headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/json, text/event-stream"}
    def call(client, name, arguments, n=[10]):
        n[0] += 1
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": n[0], "method": "tools/call", "params": {"name": name, "arguments": arguments}}, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["result"]
    with TestClient(app) as client:
        init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}, headers=headers)
        headers["MCP-Protocol-Version"] = init.json()["result"]["protocolVersion"]
        names = {t["name"] for t in client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, headers=headers).json()["result"]["tools"]}
        assert {"list_credentials", "get_credential", "put_credential", "delete_credential", "credential_audit"} <= names
        put = call(client, "put_credential", {"service": "Neon", "fields": {"password": SECRET}, "project": "secretless"})
        assert not put.get("isError"), put
        listed = call(client, "list_credentials", {"query": "neon"})
        assert SECRET not in json.dumps(listed)
        got = call(client, "get_credential", {"credential": "Neon", "reason": "connect to db"})
        assert SECRET in json.dumps(got)
        audit = json.dumps(call(client, "credential_audit", {}))
        assert "static-token" in audit and SECRET not in audit
        status = call(client, "memory_status", {})
        assert json.loads(status["content"][0]["text"])["credentials"] == 1
