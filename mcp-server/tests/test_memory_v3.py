from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from memory_mcp.memory import Memory, PART_LIMIT, norm_remote
from memory_mcp.store import Store
from memory_mcp.vault import Vault, new_key


def make(tmp_path, vault=False):
    store = Store(tmp_path / "db")
    return store, Memory(store, Vault(tmp_path / "db", new_key()) if vault else None)


def note(mem, title="Kelp timer is inverted", content="The kelp box timer output side is inverted; pulses leave on the left.",
         type="gotcha", scope="project:atm10", **kw):
    return mem.remember(title, content, type, scope, surface="test", **kw)


def test_v2_database_upgrades_in_place_and_concurrently(tmp_path):
    store = Store(tmp_path / "db")
    legacy = store.save_note("RUNBOOK: MALS-14", "Panel at godlike.host", "project_update")
    plain = store.save_note("Deploy note", "Deployed 2026-10-13", "project_update")
    with sqlite3.connect(tmp_path / "db" / "memory.sqlite3") as con:
        con.executescript("DROP TABLE note_meta; DROP TABLE projects; DROP TABLE changes; PRAGMA user_version=2;")
    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(lambda _: Store(tmp_path / "db"), range(4)))
    assert stores[0].status()["schema_version"] == 3
    mem = Memory(stores[0])
    assert mem.get_note(legacy["note_id"])["type"] == "runbook"
    assert mem.get_note(plain["note_id"])["type"] == "fact"
    assert mem.list_notes()["total"] == 2
    with sqlite3.connect(tmp_path / "db" / "memory.sqlite3") as con:
        con.execute("PRAGMA user_version=9")
    with pytest.raises(RuntimeError):
        Store(tmp_path / "db")


def test_remember_dedupes_revises_and_forces(tmp_path):
    store, mem = make(tmp_path)
    first = note(mem, cwd=r"~/agent-home\projects\atm10")
    assert first["status"] == "saved" and "undo #" in first["receipt"]
    dup = note(mem, title="Kelp timer inverted")
    assert dup["status"] == "possible_duplicate" and dup["candidates"][0]["note_id"] == first["note_id"]
    assert mem.list_notes()["total"] == 1
    body_dup = note(mem, title="Smokehouse wiring", content="The kelp box timer output side is inverted; pulses leave on the left side.")
    assert body_dup["status"] == "possible_duplicate"
    assert note(mem, title="Kelp timer inverted", scope="global")["status"] == "saved"  # other scope: no clash
    forced = note(mem, title="Kelp timer inverted", force_new=True)
    assert forced["status"] == "saved"
    revised = note(mem, content="Fixed by flipping the comparator.", note_id=first["note_id"], expected_version=first["version"])
    assert revised["receipt"].startswith("📝 revised")
    with pytest.raises(ValueError):
        note(mem, content="stale write", note_id=first["note_id"], expected_version=first["version"])
    with pytest.raises(ValueError):
        note(mem, scope="Project:Bad Key")
    with pytest.raises(ValueError):
        note(mem, type="musing")
    assert mem.get_project("atm10")["path_globs"] == ["c:/users/agent/projects/atm10/**"]


def test_remember_scrubs_vault_secrets_and_token_patterns(tmp_path):
    store, mem = make(tmp_path, vault=True)
    mem.vault.put("Example API", {"api_key": "zq9-SECRET-VALUE-77xx"}, client_id="test")
    saved = mem.remember("Deploy key", "Use zq9-SECRET-VALUE-77xx and ghp_abcdefghijklmnopqrstuv1234", "fact", surface="test")
    assert saved["redacted"] == 2
    text = mem.get_note(saved["note_id"])["content"]
    assert "zq9-SECRET" not in text and "ghp_" not in text and "[REDACTED:vault:Example API]" in text


def test_failed_metadata_write_rolls_back_the_source(tmp_path):
    store, mem = make(tmp_path)
    def boom(con, version, previous):
        raise RuntimeError("metadata failure")
    with pytest.raises(RuntimeError):
        store.save_note("Orphan", "should vanish", "project_update", on_commit=boom)
    assert store.status()["sources"] == 0
    assert store.search("vanish")["results"] == []


def test_revert_every_operation(tmp_path):
    store, mem = make(tmp_path)
    first = note(mem)
    nid = first["note_id"]
    rev = mem.remember("Kelp timer fixed", "Comparator flipped; timer now correct.", "decision", "project:atm10",
                       note_id=nid, expected_version=first["version"], surface="test")
    with pytest.raises(ValueError):
        mem.revert_change(first["change_id"])  # later changes exist
    back = mem.revert_change(rev["change_id"])
    restored = mem.get_note(nid)
    assert restored["title"] == "Kelp timer is inverted" and restored["type"] == "gotcha"
    assert restored["content"].startswith("The kelp box timer") and restored["evidence_type"] == "project_update"
    with pytest.raises(ValueError):
        mem.revert_change(rev["change_id"])  # already reverted
    mem.revert_change(back["change_id"])  # redo
    assert mem.get_note(nid)["title"] == "Kelp timer fixed"
    verified = mem.verify_note(nid)
    mem.revert_change(verified["change_id"])
    archived = mem.archive_note(nid, "done")
    assert mem.get_note(nid)["status"] == "archived"
    mem.revert_change(archived["change_id"])
    assert mem.get_note(nid)["status"] == "active"
    relabel = mem.set_meta(nid, pinned=True, scope="global")
    assert mem.get_note(nid)["scope"] == "global"
    mem.revert_change(relabel["change_id"])
    assert mem.get_note(nid)["scope"] == "project:atm10"
    other = note(mem, title="Smokehouse output chest", content="Smokehouse outputs to the Tom's chest at the north wall.")
    mem.revert_change(other["change_id"])  # revert of create archives
    assert mem.get_note(other["note_id"])["status"] == "archived"
    mem.delete_note(nid, reason="test")
    deleted = mem.list_changes(note_id=nid)["changes"][0]
    assert deleted["op"] == "delete"
    with pytest.raises(ValueError):
        mem.revert_change(deleted["id"])


def test_archive_hides_from_search_and_boot_but_stays_listable(tmp_path):
    store, mem = make(tmp_path)
    saved = note(mem)
    mem.archive_note(saved["note_id"])
    assert store.search("kelp")["results"] == []
    assert store.search("kelp", include_archived=True)["results"]
    assert "Kelp timer" not in mem.boot("project", project="atm10")
    assert mem.list_notes(status="archived")["total"] == 1
    mem.restore_note(saved["note_id"])
    assert "Kelp timer" in mem.boot("project", project="atm10")


def test_private_notes_stay_out_of_boot_and_untrusted_reads(tmp_path):
    store, mem = make(tmp_path)
    secret = mem.remember("Health note", "Private medical detail about Bash", "fact", sensitivity="private", surface="test")
    assert "medical" not in mem.boot("all")
    assert store.search("medical")["results"]
    assert store.search("medical", trusted=False)["results"] == []
    assert store.list_sources(kind="note", trusted=False)["sources"] == []
    with pytest.raises(ValueError):
        store.read(secret["version"], trusted=False)
    with pytest.raises(ValueError):
        mem.get_note(secret["note_id"], trusted=False)
    assert mem.list_changes(trusted=False)["changes"] == []


def test_project_resolution(tmp_path):
    store, mem = make(tmp_path)
    mem.set_project("example", "Example site", path_globs=["~/agent-home/projects/example.site/**"],
                    git_remotes=["git@github.com:you/example.git"], aliases=["example-root"])
    mem.set_project("projects", path_globs=["c:/users/agent/projects/**"])
    assert mem.resolve_project(cwd=r"~/agent-home\projects\example.site\src")["key"] == "example"
    assert mem.resolve_project(cwd=r"~/agent-home\projects\other")["key"] == "projects"
    assert mem.resolve_project(cwd=r"~/agent-home") is None
    assert mem.resolve_project(cwd="d:/elsewhere", git_remote="https://github.com/you/example")["key"] == "example"
    assert mem.resolve_project(cwd="d:/clone/example-root")["key"] == "example"
    assert mem.resolve_project(project="project:example")["key"] == "example"
    assert norm_remote("ssh://git@github.com/a/b.git") == "github.com/a/b"
    assert "No project registered" in mem.boot("project", cwd="d:/nowhere")


def test_boot_parts_fit_hook_limit_and_flag_stale(tmp_path):
    store, mem = make(tmp_path, vault=True)
    for i in range(60):
        mem.remember(f"Gotcha number {i} about subsystem {i}", ("Long detail line about subsystem %d. " % i) * 40,
                     "gotcha", "project:big", surface="test", force_new=True)
        if i < 10:
            mem.remember(f"Preference {i}", f"Bash likes option {i} " * 20, "preference", surface="test", force_new=True)
        mem.remember(f"RUNBOOK: server {i}", f"Host server{i}.example; panel at port {i}", "runbook", "project:big", surface="test", force_new=True)
        mem.vault.put(f"Service {i}", {"token": f"value-{i}-xxxxxxxx"}, project="big", client_id="test")
    old = mem.remember("Old fact", "Server IP was 10.0.0.1", "fact", surface="test", verified_at="2025-01-01T00:00:00+00:00")
    for part in ("profile", "infra", "project", "threads"):
        text = mem.boot(part, project="big")
        assert len(text) <= PART_LIMIT, (part, len(text))
    assert "more not shown" in mem.boot("project", project="big") or "More notes" in mem.boot("project", project="big")
    assert "] ⚠ UNVERIFIED" in mem.boot("profile") and old["note_id"][:8] in mem.boot("profile")
    assert "Vault services" in mem.boot("infra")
    assert "Vault services" not in Memory(store).boot("infra")
    assert mem.verify_note(old["note_id"])
    assert "] ⚠ UNVERIFIED" not in mem.boot("profile")


def test_short_ids_resolve(tmp_path):
    store, mem = make(tmp_path)
    saved = note(mem)
    assert mem.resolve_id(saved["note_id"][:8]) == saved["note_id"]
    with pytest.raises(ValueError):
        mem.resolve_id("zz")
