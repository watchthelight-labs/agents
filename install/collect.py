#!/usr/bin/env python3
# <wtl> project: agents | file: install/collect.py | author: watchthelight </wtl>
"""Copy the published parts of Bash's setup into this repo: skills, hooks, statusline, theme, the memory MCP
server. Only what install/manifest.json lists is copied; text files get the manifest's replacements; then
tools/scan.py runs over the result. Nothing is committed.

  python install/collect.py [--only claude|project|mcp] [--dry-run]

Run it on the machine that has the originals (the Windows side of the Legion today). Paths starting with ~ are
the current user's home.
"""
import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN = json.loads((ROOT / "install" / "manifest.json").read_text(encoding="utf-8"))
# Home paths, the owner's e-mail, the server address: the values to replace are themselves private, so they
# live outside the repo. Without the file nothing is collected.
PRIVATE = Path.home() / ".config" / "agents" / "private.json"
if not PRIVATE.exists():
    sys.exit(f"missing {PRIVATE}: copy it from the private project repo first")
MAN["replace"] = json.loads(PRIVATE.read_text(encoding="utf-8"))["replace"]
TEXT_EXT = {".py", ".js", ".mjs", ".ts", ".tsx", ".json", ".md", ".txt", ".toml", ".yml", ".yaml", ".sh", ".ps1",
            ".conf", ".service", ".timer", ".html", ".css", ".cfg", ".ini", ".lock", ""}


def home(p: str) -> Path:
    return Path(p.replace("~", str(Path.home()), 1)) if p.startswith("~") else Path(p)


def excluded(path: Path) -> bool:
    return any(fnmatch.fnmatch(part, pat) for part in path.parts for pat in MAN["exclude"])


def copy(src: Path, dst: Path, extra, dry: bool, log):
    if excluded(src):
        return
    if dry:
        log.append(f"would copy {src} -> {dst.relative_to(ROOT)}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in TEXT_EXT:
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, dst)
            return
        for old, new in MAN["replace"] + extra:
            text = text.replace(old, new)
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        shutil.copy2(src, dst)
    log.append(f"copied {dst.relative_to(ROOT)}")


def copy_dir(src: Path, dst: Path, extra, dry, log):
    if not src.exists():
        log.append(f"MISSING {src}")
        return
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        copy(f, dst / f.relative_to(src), extra, dry, log)


def synced_root() -> Path:
    base = home("~/.claude/skills/synced")
    dirs = [d for d in base.iterdir() if d.is_dir()] if base.exists() else []
    return dirs[0] if dirs else base


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["claude", "project", "mcp"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    log = []
    if a.only in (None, "claude"):
        c = MAN["claude"]
        root = home(c["root"])
        for s, d in c["files"].items():
            copy(root / s, ROOT / d, [], a.dry_run, log)
        for s, d in c["skill_dirs"].items():
            copy_dir(root / s, ROOT / d, [], a.dry_run, log)
        for s, d in c["synced_skills"].items():
            copy_dir(synced_root() / s, ROOT / d, [], a.dry_run, log)
    if a.only in (None, "project"):
        p = MAN["project_skills"]
        for s, d in p["skill_dirs"].items():
            copy_dir(home(p["root"]) / s, ROOT / d, [], a.dry_run, log)
    if a.only in (None, "mcp"):
        m = MAN["mcp_server"]
        src = home(m["root"])
        tracked = subprocess.run(["git", "ls-files"], cwd=src, capture_output=True, text=True).stdout.splitlines()
        for rel in tracked:
            if rel in m.get("skip", []):   # files this repo writes itself (the public setup guide)
                continue
            out = rel
            for old, new in m["replace"]:   # file names carry the domain too (nginx site files)
                out = out.replace(old, new)
            copy(src / rel, ROOT / m["dst"] / out, m["replace"], a.dry_run, log)
    print("\n".join(log[-40:]) if a.dry_run else f"{sum(1 for l in log if l.startswith('copied'))} file(s) copied")
    missing = [l for l in log if l.startswith("MISSING")]
    if missing:
        print("\n".join(missing))
    if not a.dry_run:
        rc = subprocess.run([sys.executable, str(ROOT / "tools" / "scan.py")], cwd=ROOT).returncode
        sys.exit(rc)


if __name__ == "__main__":
    main()
