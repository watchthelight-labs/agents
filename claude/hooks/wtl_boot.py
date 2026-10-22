#!/usr/bin/env python3
"""SessionStart: inject one part of the watchthelight boot context.

    wtl_boot.py profile|infra|project|threads

Four settings entries run in parallel, each under Claude Code's 10,000-character
hook-output limit, so together they carry ~36k characters of memory. Each part
is cached per folder; when the server is unreachable the cached copy is shown
with a banner. Never blocks or fails a session.
"""

import hashlib, json, os, subprocess, sys, time
import urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

PARTS = ("profile", "infra", "project", "threads")
WTL_DIR = os.path.join(H.STATE_DIR, "wtl")
DEFAULT_URL = "https://mcp.watchthelight.org"
LIMIT = 9900


def token():
    """Bearer token: ~/.claude/state/wtl/token, else the watchthelight entry in ~/.claude.json."""
    try:
        with open(os.path.join(WTL_DIR, "token"), "r", encoding="utf-8") as f:
            value = f.read().strip()
            if value:
                return value.removeprefix("Bearer ").strip()
    except OSError:
        pass
    env = os.environ.get("WTL_TOKEN", "").strip()
    if env:
        return env
    # ~/.claude.json is large and rewritten while sessions start; a half-written read just falls through.
    cfg = H.load_json(os.path.join(os.path.expanduser("~"), ".claude.json"), {})
    for name, server in (cfg.get("mcpServers") or {}).items():
        url = str((server or {}).get("url") or "")
        if name == "watchthelight" or "mcp.watchthelight.org" in url:
            auth = ((server or {}).get("headers") or {}).get("Authorization", "")
            if auth:
                return auth.removeprefix("Bearer ").strip()
    return ""


def base_url():
    return (os.environ.get("WTL_URL") or DEFAULT_URL).rstrip("/")


def git_remote(cwd, key):
    """origin URL for cwd, cached per folder (git is slow to spawn on Windows)."""
    path = os.path.join(WTL_DIR, f"remote-{key}")
    try:
        if time.time() - os.path.getmtime(path) < 7 * 86400:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except OSError:
        pass
    remote = ""
    try:
        out = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True,
                             timeout=2, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if out.returncode == 0:
            remote = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(remote)
    except OSError:
        pass
    return remote


def fetch(part, cwd, remote):
    query = urllib.parse.urlencode({"part": part, "cwd": cwd, "git_remote": remote, "surface": "claude-code"})
    req = urllib.request.Request(f"{base_url()}/boot?{query}", headers={
        "Authorization": "Bearer " + token(), "User-Agent": "wtl-boot-hook/1"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        return resp.read().decode("utf-8")


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else ""
    if part not in PARTS:
        return
    data = H.read_input()
    if data.get("source") == "resume":
        return  # the resumed conversation already carries its boot context
    cwd = data.get("cwd") or os.getcwd()
    os.makedirs(WTL_DIR, exist_ok=True)
    key = hashlib.sha1(os.path.normcase(os.path.abspath(cwd)).encode("utf-8")).hexdigest()[:12]
    cache = os.path.join(WTL_DIR, f"{part}-{key}.md" if part == "project" else f"{part}.md")
    remote = git_remote(cwd, key) if part == "project" else ""
    text = ""
    try:
        text = fetch(part, cwd, remote)
        tmp = cache + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, cache)
    except Exception as exc:  # network, auth, TLS: fall back to the cache
        try:
            with open(cache, "r", encoding="utf-8") as f:
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(cache)))
                text = f"(watchthelight unreachable: {type(exc).__name__}; cached copy from {stamp})\n" + f.read()
        except OSError:
            if part == "profile":
                text = (f"(watchthelight unreachable at session start: {type(exc).__name__}. Call the watchthelight "
                        "boot tool once it responds; remember still applies.)")
    if part == "threads" and data.get("source") == "compact" and text:
        text += ("\n\nContext was just compacted: if work before the compaction produced durable facts "
                 "(decisions, fixes, gotchas, status changes, open loops), save them with remember now.")
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": text[:LIMIT]}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
