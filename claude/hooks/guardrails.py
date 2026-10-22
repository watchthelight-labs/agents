#!/usr/bin/env python3
"""PreToolUse guardrail: regex rules in ~/.claude/guardrails.json.

A matching rule answers deny (Claude must ask you in chat) or ask (permission
prompt). Silent on no match. Every decision is also logged to cmdlog.jsonl.
"""

import json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

RULES = os.path.join(H.CLAUDE_DIR, "guardrails.json")


def check_fires(check):
    """Optional live probe: the rule fires only when the command's exit code
    equals deny_if_exit (default 0)."""
    cmd = (check or {}).get("cmd")
    if not cmd:
        return True
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           timeout=float(check.get("timeout", 5)))
        return r.returncode == int(check.get("deny_if_exit", 0))
    except Exception:
        return bool(check.get("fire_on_error", False))


def main():
    d = H.read_input()
    tool = d.get("tool_name") or ""
    inp = d.get("tool_input") or {}
    cwd = d.get("cwd") or ""
    subj = H.subject_of(tool, inp)
    cfg = H.load_json(RULES, {})
    for rule in cfg.get("rules") or []:
        if not rule.get("enabled", True):
            continue
        tools = rule.get("tools") or "*"
        if tools != "*" and tool not in tools:
            continue
        try:
            if not re.search(rule.get("pattern") or "(?!)", subj, re.I | re.S):
                continue
            unl = rule.get("unless")
            if unl and re.search(unl, subj + "\n" + cwd, re.I | re.S):
                continue
            cw = rule.get("cwd")
            if cw and not re.search(cw, cwd, re.I):
                continue
        except re.error:
            continue
        if rule.get("check") and not check_fires(rule["check"]):
            continue
        action = rule.get("action") or cfg.get("default_action") or "deny"
        if action not in ("deny", "ask"):
            action = "deny"
        name = rule.get("name", "rule")
        reason = f"[guardrail:{name}] {rule.get('reason', 'blocked by guardrail')}"
        if action == "deny":
            reason += (" Do not retry or work around this; ask the user in chat "
                       "and wait for an explicit go-ahead.")
        H.append_jsonl(H.CMDLOG, {
            "ts": time.time(), "sess": (d.get("session_id") or "")[:8], "cwd": cwd,
            "tool": tool, "cmd": subj[:500], "event": "guardrail",
            "rule": name, "decision": action, "ok": False})
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": action,
            "permissionDecisionReason": reason}}))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
