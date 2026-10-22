import argparse
import json
import os
from pathlib import Path
import re
import sys

from .redact import scrub
from .store import EVIDENCE_TYPES, KINDS, Store, now, source_kind

FRONT_KEYS = {"kind", "evidence_type", "source_date", "title"}


def front_matter(path):
    """Optional `---` header (or a leading `kind:` line) that labels an inbox file."""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        head = handle.read(4096)
    lines = head.splitlines()
    if lines and lines[0].strip() == "---":
        try:
            lines = lines[1:lines.index("---", 1)]
        except ValueError:
            return {}
    elif not (lines and lines[0].lower().startswith("kind:")):
        return {}
    meta = {}
    for line in lines:
        key, sep, value = line.partition(":")
        key, value = key.strip().lower(), value.strip().strip("\"'")
        if sep and key in FRONT_KEYS and value:
            meta[key] = value
    if meta.get("kind") not in KINDS - {"note"}:
        meta.pop("kind", None)
    if meta.get("evidence_type") not in EVIDENCE_TYPES:
        meta.pop("evidence_type", None)
    return meta


def load_vault(store):
    key = os.environ.get("MEMORY_VAULT_KEY")
    if not key:
        return None
    from .vault import Vault
    return Vault(store.root, key)


def import_directory(store, root, namespace, vault=None):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Import root must be a directory")
    with store.connection() as con:
        run_id = con.execute("INSERT INTO import_runs(namespace,started_at) VALUES (?,?)", (namespace, now())).lastrowid
    scanned = changed = errors = 0
    exact = vault.secret_values() if vault is not None and namespace == "inbox" else None
    transform = (lambda text: scrub(text, exact)[0]) if namespace == "inbox" else None
    # Curated records become available first during the initial import.
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".json", ".jsonl", ".csv"}:
            continue
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        scanned += 1
        try:
            meta = front_matter(path) if namespace == "inbox" else {}
            result = store.ingest(path, f"{namespace}/{relative}", meta.get("kind", source_kind(relative)),
                                  meta.get("evidence_type", "historical_mixed"), meta.get("source_date"),
                                  meta.get("title"), transform=transform)
            changed += int(result["changed"])
        except (OSError, UnicodeError, ValueError) as exc:
            errors += 1
            print(json.dumps({"source": relative, "error": type(exc).__name__}), file=sys.stderr, flush=True)
        if scanned % 250 == 0:
            with store.connection() as con:
                con.execute("UPDATE import_runs SET scanned=?,changed=?,errors=? WHERE id=?", (scanned, changed, errors, run_id))
            print(json.dumps({"scanned": scanned, "changed": changed, "errors": errors}), flush=True)
    with store.connection() as con:
        con.execute("UPDATE import_runs SET finished_at=?,scanned=?,changed=?,errors=? WHERE id=?", (now(), scanned, changed, errors, run_id))
        # A full-index optimize holds the write lock for a long time; the library import runs it once at the end,
        # inbox imports leave it to the nightly `memory-mcp optimize` so note writes never stall behind it.
        if changed and namespace == "library":
            con.execute("INSERT INTO passages(passages) VALUES ('optimize')")
    print(json.dumps({"complete": True, "scanned": scanned, "changed": changed, "errors": errors}), flush=True)
    return 1 if errors else 0


def leak_scan(store, vault):
    """FTS phrase lookup per secret, confirmed by exact substring match on the passage."""
    leaks = {}
    with store.connection() as con:
        for value, service in vault.secret_values().items():
            words = re.findall(r"[^\W_]+", value, re.UNICODE)
            if not words:
                continue
            rows = con.execute("""SELECT s.uri,c.text FROM passages JOIN chunks c ON c.id=passages.rowid
                JOIN sources s ON s.document_id=c.document_id WHERE passages MATCH ? LIMIT 200""",
                               ('"' + " ".join(words) + '"',)).fetchall()
            for uri, text in rows:
                if value in text:
                    leaks.setdefault(uri, set()).add(service)
    return {"sources_with_secrets": len(leaks), "leaks": [{"source": uri, "services": sorted(v)} for uri, v in sorted(leaks.items())]}


def seed_contacts(store, path):
    """Load threads, people and follows from a JSON file; safe to run again (existing threads get no second message)."""
    from .contacts import Contacts
    from .memory import Memory
    contacts = Contacts(store, Memory(store, load_vault(store)))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    done = {"threads": 0, "people": 0, "follows": 0, "errors": []}
    for p in data.get("people", []):
        try:
            contacts.set_person(p["handle"], p.get("display"), p.get("notes"), p.get("also"), p.get("sensitivity"), "seed")
            done["people"] += 1
        except (KeyError, ValueError) as exc:
            done["errors"].append(f"person {p.get('handle')}: {exc}")
    for t in data.get("threads", []):
        t = dict(t)
        with store.connection() as con:
            exists = contacts.thread_row(con, t.get("thread_id"), t.get("url")) is not None
        if exists and not (t.get("url") or "").count("#issuecomment-"):
            t.pop("summary", None)
        try:
            contacts.log_contact(surface="seed", origin="seed", **t)
            done["threads"] += 1
        except (TypeError, ValueError) as exc:
            done["errors"].append(f"thread {t.get('url') or t.get('title')}: {exc}")
    for f in data.get("follows", []):
        try:
            contacts.follow(f["target"], f.get("kind"), f.get("cadence_minutes"), True, None, f.get("project"), "seed", origin="seed")
            done["follows"] += 1
        except (KeyError, ValueError) as exc:
            done["errors"].append(f"follow {f.get('target')}: {exc}")
    return done


def main():
    parser = argparse.ArgumentParser(description="Private MCP memory archive")
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("MEMORY_DATA", "data")))
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8091)
    dash = sub.add_parser("dash", help="Dashboard API for dash.example.org (127.0.0.1 only)")
    dash.add_argument("--port", type=int, default=8092)
    ingest = sub.add_parser("import")
    ingest.add_argument("directory", type=Path)
    ingest.add_argument("--namespace", choices=["library", "inbox"], default="inbox")
    sub.add_parser("status")
    sub.add_parser("optimize", help="Merge FTS index segments (nightly, after the backup)")
    check = sub.add_parser("check")
    forget = sub.add_parser("forget")
    forget.add_argument("uri")
    forget.add_argument("--keep-history", action="store_true")
    vault = sub.add_parser("vault")
    vault_sub = vault.add_subparsers(dest="vault_command", required=True)
    vault_import = vault_sub.add_parser("import", help="Upsert credentials from a JSON list on stdin")
    vault_import.add_argument("source", choices=["-"])
    vault_sub.add_parser("list")
    vault_sub.add_parser("leak-scan", help="Report archive sources containing exact vault secrets (never prints values)")
    vault_sub.add_parser("new-key")
    poll = sub.add_parser("poll", help="Check followed GitHub threads, repos and searches (GITHUB_POLL_TOKEN, GITHUB_SELF)")
    poll.add_argument("--dry-run", action="store_true", help="Fetch and report, write nothing")
    poll.add_argument("--follow", type=int, help="Check this follow id now, whether due or not")
    poll.add_argument("--budget", type=int, default=400)
    people = sub.add_parser("contacts")
    people_sub = people.add_subparsers(dest="contacts_command", required=True)
    seed = people_sub.add_parser("seed", help="Load threads, people and follows from a JSON file (idempotent)")
    seed.add_argument("file", type=Path)
    erase = people_sub.add_parser("forget-person", help="Erase a person and their handles (platform:handle)")
    erase.add_argument("handle")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .server import create_app
        token = os.environ.get("MEMORY_TOKEN", "")
        app = create_app(args.data, token)
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning", proxy_headers=False)
        return
    if args.command == "dash":
        import uvicorn
        from .dash import create_dash
        uvicorn.run(create_dash(args.data), host="127.0.0.1", port=args.port, access_log=False, log_level="warning",
                    proxy_headers=False)
        return
    if args.command == "vault" and args.vault_command == "new-key":
        from .vault import new_key
        print(new_key())
        return
    store = Store(args.data)
    if args.command == "import":
        sys.exit(import_directory(store, args.directory, args.namespace, load_vault(store)))
    elif args.command == "forget":
        print(json.dumps(store.forget(args.uri, not args.keep_history)))
    elif args.command == "vault":
        vault = load_vault(store)
        if vault is None:
            raise SystemExit("MEMORY_VAULT_KEY is not set")
        if args.vault_command == "list":
            print(json.dumps(vault.list(limit=10000), indent=2))
            return
        if args.vault_command == "leak-scan":
            print(json.dumps(leak_scan(store, vault), indent=2))
            return
        created = updated = 0
        failed = []
        for index, item in enumerate(json.load(sys.stdin)):
            try:
                result = vault.put(item["service"], item["fields"], item.get("label", ""), item.get("project", ""),
                                   item.get("tags"), item.get("secret_fields"), item.get("source_path"),
                                   client_id="cli-import", upsert=True)
            except (KeyError, ValueError) as exc:
                failed.append({"index": index, "service": str(item.get("service", ""))[:80], "error": str(exc)})
                continue
            created += result["created"]
            updated += not result["created"]
        print(json.dumps({"created": created, "updated": updated, "failed": failed, "total": vault.count()}))
        if failed:
            sys.exit(1)
    elif args.command == "poll":
        from .contacts import Contacts
        from .github_poll import GitHub, Poller
        from .memory import Memory
        contacts = Contacts(store, Memory(store, load_vault(store)))
        gh = GitHub(os.environ.get("GITHUB_POLL_TOKEN", ""), budget=args.budget)
        selfs = os.environ.get("GITHUB_SELF", "watchthelight").split(",")
        result = Poller(contacts, gh, selfs, dry_run=args.dry_run).run(only=args.follow)
        print(json.dumps(result, indent=2))
        if result.get("errors") and not result.get("paused_until"):
            sys.exit(1)
    elif args.command == "contacts":
        if args.contacts_command == "seed":
            result = seed_contacts(store, args.file)
        else:
            from .contacts import Contacts
            from .memory import Memory
            result = Contacts(store, Memory(store)).forget_person(args.handle)
        print(json.dumps(result, indent=2))
    elif args.command == "optimize":
        with store.connection() as con:
            con.execute("INSERT INTO passages(passages) VALUES ('optimize')")
        print(json.dumps({"optimized": True}))
    elif args.command == "check":
        with store.connection() as con:
            result = con.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(result)
            con.execute("INSERT INTO passages(passages,rank) VALUES ('integrity-check',1)")
        print(json.dumps({"sqlite": "ok", "fts": "ok"}))
    else:
        print(json.dumps(store.status(), indent=2))


if __name__ == "__main__":
    main()
