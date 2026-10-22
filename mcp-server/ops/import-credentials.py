"""Parse markdown credential files and upsert them into the server vault over SSH.

Dry run (default) prints names and field labels only. --apply pipes JSON over SSH
stdin into `memory-mcp vault import -`, so plaintext never lands on server disk.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memory_mcp.vault import default_secret_fields  # noqa: E402

KEY = "~/.ssh/memory-server.pem"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-i", KEY, "my-server"]
REMOTE = ("sudo systemd-run --quiet --pipe --wait --collect -p User=memory-mcp -p Group=memory-mcp "
          "-p EnvironmentFile=/etc/memory-mcp.env -p UMask=0077 "
          "/srv/memory-mcp/venv/bin/memory-mcp --data /srv/memory-mcp/data vault import -")
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
FIELD = re.compile(r"^\s*(?:[-*+]|\d+\.)?\s*(?:\*\*|__)?([^:*|`=]{1,80}?)(?:\*\*|__)?\s*:\s*(?:\*\*|__)?\s*(.+?)\s*$")
ENV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]{1,80})\s*=\s*(.+?)\s*$")
TABLE = re.compile(r"^\s*\|(.+)\|\s*$")


def clean(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        value = value[1:-1]
    return value.strip("`").strip()


def parse(path, project):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    items, stack = [], []
    current = {"heading": [], "fields": {}, "notes": []}

    def flush():
        if current["fields"] or any(n.strip() for n in current["notes"]):
            heads = current["heading"] or [path.stem]
            fields = dict(current["fields"])
            notes = "\n".join(current["notes"]).strip()
            if notes:
                fields["notes" if "notes" not in fields else "notes (freeform)"] = notes
            items.append({"project": project, "service": heads[0], "label": " / ".join(heads[1:]),
                          "fields": fields, "source_path": str(path),
                          "secret_fields": default_secret_fields(list(fields)) + (["notes" if "notes" in fields else "notes (freeform)"] if notes else [])})

    def add(name, value):
        name = re.sub(r"\s+", " ", name.strip().strip("*_ ")) or "value"
        base, n = name, 2
        while name in current["fields"]:
            name, n = f"{base} ({n})", n + 1
        current["fields"][name] = clean(value)

    fence = False
    lines = text.splitlines()
    if lines and lines[0].strip() == "---" and "---" in lines[1:]:
        lines = lines[lines.index("---", 1) + 1:]  # YAML front matter is document metadata, not a credential.
    for line in lines:
        if line.strip().startswith("```"):
            fence = not fence
            current["notes"].append(line)
            continue
        if fence:
            current["notes"].append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            # A single top-level title is the document name; services start at the next level.
            stack = [h for h in stack if h[0] < level] + [(level, heading.group(2).strip("*_ "))]
            top = min(h[0] for h in stack)
            heads = [h[1] for h in stack if not (h[0] == 1 and top == 1 and len(stack) > 1)]
            current = {"heading": heads, "fields": {}, "notes": []}
            continue
        table = TABLE.match(line)
        if table:
            cells = [c.strip() for c in table.group(1).split("|")]
            if len(cells) == 2 and not set("".join(cells)) <= set("-: ") and cells[0].lower() not in {"field", "key", "name", "item"}:
                add(cells[0], cells[1])
            elif not set("".join(cells)) <= set("-: "):
                current["notes"].append(line)
            continue
        field = FIELD.match(line)
        if field and not field.group(2).startswith("//") and not re.match(r"https?$", field.group(1).strip(), re.I):
            add(field.group(1), field.group(2))
            continue
        env = ENV.match(line)
        if env:
            add(env.group(1), env.group(2))
            continue
        if line.strip() and not re.fullmatch(r"\s*(?:-{3,}|\*{3,})\s*", line):
            current["notes"].append(line)
    flush()
    return items


def parse_csv(path, project):
    """Browser password exports: name,url,username,password,note."""
    items = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("password") and not row.get("note"):
                continue
            fields = {k: row[k] for k in ("url", "username", "password", "note") if row.get(k)}
            items.append({"project": project, "service": row.get("name") or row.get("url") or "unnamed",
                          "label": row.get("username", ""), "fields": fields, "source_path": str(path),
                          "secret_fields": [f for f in ("password", "note") if f in fields]})
    return items


def parse_raw(path, project):
    return [{"project": project, "service": path.stem, "label": "", "source_path": str(path),
             "fields": {"contents": path.read_text(encoding="utf-8-sig", errors="replace").strip()}, "secret_fields": ["contents"]}]


def dedupe(items):
    """One row per (project, service, label); later inputs win, older distinct values are kept as previous_*."""
    merged = {}
    for item in items:
        key = (item["project"], item["service"], item["label"])
        old = merged.get(key)
        if old:
            for name, value in old["fields"].items():
                if name not in item["fields"]:
                    item["fields"][name] = value
                    if name in old["secret_fields"]:
                        item["secret_fields"] = sorted(set(item["secret_fields"]) | {name})
                elif item["fields"][name] != value and not name.startswith("previous ") and name != "url":
                    n, slot = 1, "previous " + name
                    while slot in item["fields"] and item["fields"][slot] != value:
                        n += 1
                        slot = f"previous {name} ({n})"
                    item["fields"][slot] = value
                    item["secret_fields"] = sorted(set(item["secret_fields"]) | ({slot} if name in old["secret_fields"] else set()))
            item["tags"] = sorted(set(old.get("tags", [])) | set(item.get("tags", [])))
        merged[key] = item
    return list(merged.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--project", help="Project name for every file (default: parent folder name)")
    parser.add_argument("--apply", action="store_true", help="Upload to the vault (default: dry run)")
    parser.add_argument("--json", type=Path, help="Write the parsed items to this local file for review/hand edits")
    parser.add_argument("--from-json", action="store_true", help="Treat each path as a reviewed JSON list instead of markdown")
    parser.add_argument("--raw", action="store_true", help="Store each file whole as one credential")
    parser.add_argument("--tags", default="", help="Comma-separated tags added to every item")
    args = parser.parse_args()
    items = []
    for path in args.paths:
        if args.from_json:
            items.extend(json.loads(path.read_text(encoding="utf-8")))
            continue
        project = args.project or path.resolve().parent.name
        path = path.resolve(strict=True)
        reader = parse_raw if args.raw else parse_csv if path.suffix.lower() == ".csv" else parse
        items.extend(reader(path, project))
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    for item in items:
        item["tags"] = sorted(set(item.get("tags") or []) | set(tags))
    for item in items:
        item["service"], item["label"] = item["service"][:200], item["label"][:200]
    items = dedupe(items)
    for item in items:
        flags = ", ".join(f + ("*" if f in item["secret_fields"] else "") for f in item["fields"])
        print(f"[{item['project']}] {item['service']}" + (f" / {item['label']}" if item["label"] else "") + f"  ->  {flags}")
    print(f"{len(items)} credentials parsed (* = treated as secret for archive scrubbing)")
    if args.json:
        args.json.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Wrote", args.json)
    if args.apply:
        result = subprocess.run(SSH + [REMOTE], input=json.dumps(items).encode(), capture_output=True)
        sys.stdout.write(result.stdout.decode(errors="replace"))
        if result.returncode:
            sys.stderr.write(result.stderr.decode(errors="replace"))
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
