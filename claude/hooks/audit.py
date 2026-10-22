#!/usr/bin/env python3
"""PostToolUse / PostToolUseFailure audit trail -> ~/.claude/cmdlog.jsonl.

One row per shell command and per file write: when, which session, cwd,
tool, the command or path, duration, success, first 200 chars of any error.
Query with `python ~/.claude/hooks/cmdlog.py` (or /cmdlog).
"""

import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402


def main():
    d = H.read_input()
    tool = d.get("tool_name") or ""
    inp = d.get("tool_input") or {}
    ev = d.get("hook_event_name") or ""
    resp = d.get("tool_response")
    ok = ev != "PostToolUseFailure"
    err = ""
    if isinstance(resp, dict):
        err = str(resp.get("stderr") or resp.get("error") or "")
        if resp.get("interrupted"):
            ok = False
            err = err or "interrupted"
        if resp.get("is_error") or resp.get("isError"):
            ok = False
    elif not ok:
        err = str(d.get("error") or resp or "")
    row = {"ts": time.time(), "sess": (d.get("session_id") or "")[:8],
           "cwd": d.get("cwd") or "", "tool": tool,
           "cmd": H.subject_of(tool, inp)[:500], "ok": ok}
    if d.get("duration_ms") is not None:
        row["dur_ms"] = d.get("duration_ms")
    if err.strip():
        row["err"] = err.strip()[:200]
    if tool in H.SHELL_TOOLS and isinstance(inp, dict) and inp.get("run_in_background"):
        row["bg"] = True
    H.append_jsonl(H.CMDLOG, row)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
