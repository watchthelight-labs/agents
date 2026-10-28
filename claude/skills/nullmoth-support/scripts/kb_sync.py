#!/usr/bin/env python3
# <wtl> project: agents | file: claude/skills/nullmoth-support/scripts/kb_sync.py | author: watchthelight </wtl>
"""Mirror every public nullmoth repo into a local, read-only knowledge base.

Per repo: a git clone of the default branch (text is searched, nothing is ever built or run), every issue and PR with
all comments rendered to markdown, and every release note. Incremental after the first run.

    python kb_sync.py            # sync if older than 6 h
    python kb_sync.py --force    # sync now
    python kb_sync.py --status   # show what is there
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OWNER = "nullmoth"
KB = Path(os.environ.get("NULLMOTH_KB", Path.home() / "src" / "nullmoth-kb"))
STATE = KB / "state.json"
MAX_AGE_H = 6


def gh_lines(path: str) -> list:
    """GET a paginated GitHub API list, one JSON object per item."""
    out = subprocess.run(["gh", "api", "--paginate", path, "--jq", ".[]"],
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path}: {out.stderr.strip()}")
    return [json.loads(l) for l in out.stdout.splitlines() if l.strip()]


def git(*args, cwd=None) -> str:
    out = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd,
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout.strip()


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"repos": {}}


def sync_code(name: str, branch: str, st: dict):
    d = KB / "repos" / name
    if not (d / ".git").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", "--filter=blob:none", "--no-tags", "-b", branch,
            f"https://github.com/{OWNER}/{name}.git", str(d))
    else:
        git("fetch", "-q", "origin", branch, cwd=d)
        git("reset", "-q", "--hard", f"origin/{branch}", cwd=d)
    st["sha"] = git("rev-parse", "HEAD", cwd=d)
    st["branch"] = branch


def who(u: dict, assoc: str) -> str:
    login = (u or {}).get("login", "ghost")
    tag = {"OWNER": " [maintainer]", "MEMBER": " [maintainer]", "COLLABORATOR": " [collaborator]"}.get(assoc, "")
    return login + tag


def sync_issues(name: str, st: dict):
    data = KB / "data" / name
    data.mkdir(parents=True, exist_ok=True)
    ipath, cpath = data / "issues.json", data / "comments.json"
    issues = json.loads(ipath.read_text(encoding="utf-8")) if ipath.exists() else {}
    comments = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    since = st.get("issues_since")
    q = f"&since={since}" if since else ""
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in gh_lines(f"repos/{OWNER}/{name}/issues?state=all&per_page=100{q}"):
        issues[str(i["number"])] = {
            "n": i["number"], "title": i["title"], "state": i["state"], "url": i["html_url"],
            "pr": "pull_request" in i, "author": who(i["user"], i.get("author_association", "")),
            "labels": [l["name"] for l in i.get("labels", [])], "created": i["created_at"][:10],
            "closed": (i.get("closed_at") or "")[:10], "reason": i.get("state_reason") or "",
            "body": i.get("body") or ""}
    for c in gh_lines(f"repos/{OWNER}/{name}/issues/comments?per_page=100{q}"):
        n = c["issue_url"].rsplit("/", 1)[1]
        lst = [x for x in comments.get(n, []) if x["id"] != c["id"]]
        lst.append({"id": c["id"], "who": who(c["user"], c.get("author_association", "")),
                    "at": c["created_at"][:10], "url": c["html_url"], "body": c.get("body") or ""})
        comments[n] = sorted(lst, key=lambda x: x["id"])
    ipath.write_text(json.dumps(issues), encoding="utf-8")
    cpath.write_text(json.dumps(comments), encoding="utf-8")
    out = KB / "issues" / name
    out.mkdir(parents=True, exist_ok=True)
    for n, i in issues.items():
        kind = "PR" if i["pr"] else "Issue"
        state = i["state"] + (f" ({i['reason']})" if i["reason"] else "")
        lines = [f"# {kind} #{n}: {i['title']}", "",
                 f"url: {i['url']}", f"state: {state}, opened {i['created']} by {i['author']}"
                 + (f", closed {i['closed']}" if i["closed"] else ""),
                 f"labels: {', '.join(i['labels']) or '-'}", "", i["body"].strip(), ""]
        for c in comments.get(n, []):
            lines += [f"## {c['who']}, {c['at']} ({c['url']})", "", c["body"].strip(), ""]
        (out / f"{n}.md").write_text("\n".join(lines), encoding="utf-8")
    st["issues_since"] = started
    st["issues"] = len(issues)


def sync_releases(name: str, st: dict):
    rel = gh_lines(f"repos/{OWNER}/{name}/releases?per_page=100")
    out = KB / "releases"
    out.mkdir(parents=True, exist_ok=True)
    lines = [f"# {OWNER}/{name} releases (newest first)", ""]
    for r in rel:
        flag = " (pre-release)" if r.get("prerelease") else ""
        assets = ", ".join(a["name"] for a in r.get("assets", []))
        lines += [f"## {r['tag_name']}{flag}, {(r.get('published_at') or '')[:10]}", "",
                  f"url: {r['html_url']}", f"assets: {assets or '-'}", "", (r.get("body") or "").strip(), ""]
    (out / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
    st["latest"] = rel[0]["tag_name"] if rel else ""
    st["releases"] = len(rel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    state = load_state()
    if a.status or (not a.force and time.time() - state.get("synced", 0) < MAX_AGE_H * 3600):
        age = (time.time() - state.get("synced", 0)) / 3600
        print(f"kb {KB}, synced {age:.1f} h ago" if state.get("synced") else f"kb {KB}: never synced")
        for n, s in state.get("repos", {}).items():
            print(f"  {n}: {s.get('sha', '')[:10]} latest {s.get('latest') or '-'}, "
                  f"{s.get('issues', 0)} issues/PRs, {s.get('releases', 0)} releases")
        return
    repos = gh_lines(f"users/{OWNER}/repos?per_page=100&type=owner")
    errors = 0
    for r in repos:
        if r.get("fork"):
            continue
        name = r["name"]
        st = state["repos"].setdefault(name, {})
        for step in (lambda: sync_code(name, r["default_branch"], st),
                     lambda: sync_issues(name, st) if r.get("has_issues") else None,
                     lambda: sync_releases(name, st)):
            try:
                step()
            except RuntimeError as e:
                errors += 1
                print(f"  {name}: {e}", file=sys.stderr)
        print(f"  {name}: {st.get('sha', '')[:10]} latest {st.get('latest') or '-'}, "
              f"{st.get('issues', 0)} issues/PRs, {st.get('releases', 0)} releases")
    for d in ("notes", "answers"):
        (KB / d).mkdir(parents=True, exist_ok=True)
    if not errors:
        state["synced"] = time.time()
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(f"synced {len(state['repos'])} repos into {KB}" + (f", {errors} error(s)" if errors else ""))


if __name__ == "__main__":
    main()
