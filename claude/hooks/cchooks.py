#!/usr/bin/env python3
"""Shared bits for the Python hooks in ~/.claude/hooks.

Every hook: reads one JSON object on stdin, never raises (a hook bug must
not block Claude), and reuses statusline.py for transcript math.
"""

import json, os, sys, time

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
HOOKS_DIR = os.path.join(CLAUDE_DIR, "hooks")
STATE_DIR = os.path.join(CLAUDE_DIR, "state")
CMDLOG = os.path.join(CLAUDE_DIR, "cmdlog.jsonl")
LEDGER = os.path.join(CLAUDE_DIR, "ledger.jsonl")

sys.path.insert(0, CLAUDE_DIR)
import statusline as sl  # noqa: E402  (also switches stdout to utf-8 on Windows)

FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")


def read_input():
    """The hook payload (empty dict on any problem)."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw and raw.strip() else {}
    except Exception:
        return {}


def subject_of(tool, inp):
    """The one string a rule or log line is about: the command, the file path,
    or the whole input as JSON."""
    if not isinstance(inp, dict):
        return str(inp or "")
    if tool in SHELL_TOOLS:
        return str(inp.get("command") or "")
    if tool in FILE_TOOLS or tool == "Read":
        return str(inp.get("file_path") or inp.get("notebook_path") or "")
    try:
        return json.dumps(inp, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(inp)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def append_jsonl(path, row):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_jsonl(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def cooldown_ok(name, secs):
    """True (and stamps) when `name` last fired more than `secs` ago."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        p = os.path.join(STATE_DIR, f"{name}.stamp")
        try:
            if time.time() - os.path.getmtime(p) < secs:
                return False
        except OSError:
            pass
        with open(p, "w") as f:
            f.write(str(time.time()))
        return True
    except OSError:
        return True


def sidecar_path(transcript_path):
    import tempfile
    sess = os.path.splitext(os.path.basename(transcript_path or ""))[0]
    return os.path.join(tempfile.gettempdir(), f"clstatus-{sess}.json")


def iter_records(path, offset=0):
    """Yield parsed transcript records from a byte offset."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            for raw in f:
                if b'"timestamp"' not in raw:
                    continue
                try:
                    yield json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
    except OSError:
        return


def prompt_text(content):
    """Plain text of a user message content (str or block list); '' for tool results."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return ""
        return "\n".join(b.get("text") or "" for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


INJECTED_PREFIXES = ("<system-reminder", "<local-command", "<command-name",
                     "<task-notification", "<command-message", "<user-prompt-submit-hook",
                     "[Request interrupted")


def is_real_prompt(rec):
    """A user record typed by the person (not tool results, meta, summaries, injected)."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary"):
        return False
    txt = prompt_text((rec.get("message") or {}).get("content")).strip()
    if not txt:
        return False
    return not txt.startswith(INJECTED_PREFIXES)
