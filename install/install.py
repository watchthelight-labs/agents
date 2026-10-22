#!/usr/bin/env python3
# <wtl> project: agents | file: install/install.py | author: watchthelight </wtl>
"""Install this repo's Claude Code setup into ~/.claude, on Windows or macOS.

  python3 install/install.py [--only skills|hooks|settings] [--dry-run] [--home PATH] [--pull]

Copies claude/skills/* to ~/.claude/skills/, claude/hooks/* to ~/.claude/hooks/, the statusline, guardrails.json,
the theme and the commands; then merges claude/settings.template.json (hook wiring and statusLine only) into
~/.claude/settings.json. Before anything changes, settings.json is copied to settings.json.bak-<time>, and a file
that would be overwritten with different content is kept as <name>.bak. Permissions, env, MCP servers, tokens
and anything else already in settings.json are left alone. Running it twice changes nothing the second time.

Things it does not do (they hold secrets, see docs/new-machine.md): the watchthelight Bearer token
(~/.claude/state/wtl/token), the MCP server entry in ~/.claude.json, notify.json (ntfy topic).
"""
import argparse
import filecmp
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "claude"
COPIES = [  # (source in repo, target under ~/.claude, kind)
    ("skills", "skills", "skills"),
    ("hooks", "hooks", "hooks"),
    ("statusline/statusline.py", "statusline.py", "hooks"),
    ("guardrails.json", "guardrails.json", "hooks"),
    ("themes", "themes", "hooks"),
    ("commands", "commands", "skills"),
]


def py_cmd() -> str:
    return "python" if platform.system() == "Windows" else "python3"


def plan_copy(src: Path, dst: Path, out: list):
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for f in files:
        t = dst if src.is_file() else dst / f.relative_to(src)
        if t.exists() and filecmp.cmp(f, t, shallow=False):
            continue
        out.append((f, t))


def merge_settings(path: Path, dry: bool) -> list:
    tpl = json.loads((CLAUDE / "settings.template.json").read_text(encoding="utf-8").replace("{PY}", py_cmd()))
    cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    before = json.dumps(cur, sort_keys=True)
    cur["statusLine"] = tpl["statusLine"]
    hooks = cur.setdefault("hooks", {})
    for event, groups in tpl["hooks"].items():
        have = hooks.setdefault(event, [])
        commands = {h.get("command") for g in have for h in g.get("hooks", [])}
        for g in groups:
            cmds = [h["command"] for h in g["hooks"]]
            if not any(c in commands for c in cmds):
                have.append(g)
    changes = [] if json.dumps(cur, sort_keys=True) == before else [f"settings.json: hook wiring and statusLine ({py_cmd()})"]
    if changes and not dry:
        if path.exists():
            shutil.copy2(path, path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["skills", "hooks", "settings"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--home", help="install into PATH/.claude instead of ~/.claude (for testing)")
    ap.add_argument("--pull", action="store_true", help="git pull this repo first")
    a = ap.parse_args()
    if a.pull:
        subprocess.run(["git", "-C", str(ROOT), "pull", "--rebase", "--autostash", "-q"], check=False)
    home = (Path(a.home) if a.home else Path.home()) / ".claude"
    todo = []
    for src, dst, kind in COPIES:
        if a.only in (None, kind):
            plan_copy(CLAUDE / src, home / dst, todo)
    for f, t in todo:
        print(f"{'would copy' if a.dry_run else 'copy'} {f.relative_to(ROOT)} -> {t}")
        if a.dry_run:
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        if t.exists():
            shutil.copy2(t, t.with_name(t.name + ".bak"))
        shutil.copy2(f, t)
    changes = merge_settings(home / "settings.json", a.dry_run) if a.only in (None, "settings") else []
    for c in changes:
        print(("would update " if a.dry_run else "updated ") + c)
    print(f"{len(todo)} file(s) {'to copy' if a.dry_run else 'copied'}, {len(changes)} settings change(s)."
          + ("" if a.dry_run else " Restart Claude Code to load them."))


if __name__ == "__main__":
    main()
