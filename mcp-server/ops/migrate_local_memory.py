"""Fold Claude Code's local auto-memory files into watchthelight notes.

    python ops/migrate_local_memory.py plan            # scan -> private/migration-plan.json (review and edit it)
    python ops/migrate_local_memory.py apply [--dry]   # send the reviewed plan through the MCP remember tool

Re-runnable: private/migration-state.json maps each file to its note and content hash, so a changed file becomes
a revision and an unchanged one is skipped. Source files are only read, never modified.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
PROJECTS = Path.home() / ".claude" / "projects"
PLAN = root / "private" / "migration-plan.json"
STATE = root / "private" / "migration-state.json"
HOME_DIRS = {"C--Users-agent", "C--Users-you"}
TYPE_MAP = {"user": "preference", "feedback": "preference", "project": "fact", "reference": "fact"}


def front_matter(text):
    """The small YAML subset these files use: top-level keys, one nested `metadata:` map, quoted strings."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta, nested = {}, None
    for line in text[3:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        value = value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip('"')
        if line.startswith((" ", "\t")) and nested is not None:
            meta[nested][key] = value
        elif value == "":
            nested = key
            meta[key] = {}
        else:
            nested = None
            meta[key] = value
    return meta, text[end + 4:].lstrip("\n")


def index_titles(folder):
    """Titles from MEMORY.md lines: - [Title](file.md) — hook"""
    titles = {}
    index = folder / "MEMORY.md"
    if index.exists():
        for m in re.finditer(r"^- \[([^\]]+)\]\(([^)]+\.md)\)", index.read_text(encoding="utf-8", errors="replace"), re.M):
            titles[m.group(2)] = m.group(1)
    return titles


def project_cwd(folder):
    """The real working directory of a Claude project folder, read from its session transcripts."""
    for transcript in sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        with transcript.open("r", encoding="utf-8", errors="replace") as handle:
            for i, line in enumerate(handle):
                if i > 200:
                    break
                if '"cwd"' in line:
                    try:
                        cwd = json.loads(line).get("cwd")
                    except ValueError:
                        continue
                    if cwd:
                        return cwd
    return None


def project_key(cwd):
    name = re.sub(r"[^a-z0-9._-]+", "-", Path(cwd).name.lower()).strip("-.")
    return name[:64] or None


def plan():
    entries, projects = [], {}
    for folder in sorted(p for p in PROJECTS.iterdir() if (p / "memory").is_dir()):
        files = [f for f in sorted((folder / "memory").glob("*.md")) if f.name != "MEMORY.md"]
        if not files:
            continue
        cwd = project_cwd(folder)
        key = None if folder.name in HOME_DIRS or not cwd else project_key(cwd)
        if key:
            seed = projects.setdefault(key, {"key": key, "title": Path(cwd).name, "path_globs": [], "aliases": [key]})
            glob = cwd.replace("\\", "/").rstrip("/").lower() + "/**"
            if glob not in seed["path_globs"]:
                seed["path_globs"].append(glob)
        titles = index_titles(folder / "memory")
        for f in files:
            text = f.read_text(encoding="utf-8", errors="replace")
            meta, body = front_matter(text)
            nested = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
            kind = nested.get("type") or meta.get("type") or "project"
            modified = nested.get("modified") or datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()
            description = meta.get("description", "")
            entries.append({
                "file": str(f), "folder": folder.name, "cwd": cwd,
                "title": titles.get(f.name) or meta.get("name", f.stem).replace("-", " ").replace("_", " "),
                "type": TYPE_MAP.get(kind, "fact"), "source_type": kind,
                "scope": f"project:{key}" if key else "global",
                "verified_on": modified[:10],
                "content": (description + "\n\n" + body.strip()).strip() if description and description not in body else body.strip(),
                "skip": False,
            })
    PLAN.parent.mkdir(exist_ok=True)
    PLAN.write_text(json.dumps({"projects": sorted(projects.values(), key=lambda p: p["key"]), "notes": entries},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(entries)} files from {len({e['folder'] for e in entries})} folders, {len(projects)} project seeds -> {PLAN}")
    for e in entries:
        print(f"  {e['scope']:<34} {e['type']:<11} {e['title'][:70]}")


async def apply(dry):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    connection = json.loads((root / "private" / "connection.json").read_text(encoding="utf-8"))
    data = json.loads(PLAN.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}

    def payload(result):
        return result.structured_content or json.loads(next(b.text for b in result.content if b.type == "text"))

    async def call_paced(client, name, arguments):
        """Stay under nginx's 10 req/s limit; retry once after a pause when a call is throttled."""
        for attempt in (1, 2, 3):
            await asyncio.sleep(0.25)
            try:
                return await client.call_tool(name, arguments)
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(5 * attempt)

    counts = {"saved": 0, "revised": 0, "unchanged": 0, "skipped": 0, "duplicate": 0, "error": 0}
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + connection["token"]}, timeout=90) as http:
        async with Client(streamable_http_client(connection["url"], http_client=http), mode="legacy") as client:
            for project in data["projects"]:
                if not dry:
                    result = await client.call_tool("set_project", {k: v for k, v in project.items() if v})
                    assert not result.is_error, result
            for e in data["notes"]:
                digest = hashlib.sha256(Path(e["file"]).read_bytes()).hexdigest()
                known = state.get(e["file"])
                if e.get("skip"):
                    counts["skipped"] += 1
                    continue
                if known and known["sha256"] == digest and known.get("plan") == hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest():
                    counts["unchanged"] += 1
                    continue
                args = {"title": e["title"][:200], "content": e["content"][:32000], "type": e["type"], "scope": e["scope"],
                        "verified_on": e["verified_on"], "origin": "migration"}
                if e.get("sensitivity"):
                    args["sensitivity"] = e["sensitivity"]
                if e.get("pinned"):
                    args["pinned"] = True
                if e.get("force_new"):
                    args["force_new"] = True
                if known:
                    current = payload(await client.call_tool("read_note", {"note_id": known["note_id"]}))
                    args.update(note_id=known["note_id"], expected_version=current["current_version"])
                if dry:
                    print("would", "revise" if known else "save", e["scope"], e["title"])
                    continue
                result = await call_paced(client, "remember", args)
                body = payload(result) if not result.is_error else {"status": "error", "text": result.content[0].text}
                if body.get("status") == "possible_duplicate":
                    counts["duplicate"] += 1
                    print("DUPLICATE?", e["title"], "->", [(c["title"], c["note_id"][:8], c["score"]) for c in body["candidates"]])
                    continue
                if body.get("status") != "saved":
                    counts["error"] += 1
                    print("ERROR", e["title"], body)
                    continue
                counts["revised" if known else "saved"] += 1
                print(body["receipt"])
                state[e["file"]] = {"sha256": digest, "note_id": body["note_id"], "version": body["version"],
                                    "plan": hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()}
                STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(counts))


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["plan", "apply"])
parser.add_argument("--dry", action="store_true")
args = parser.parse_args()
if args.command == "plan":
    plan()
else:
    asyncio.run(apply(args.dry))
