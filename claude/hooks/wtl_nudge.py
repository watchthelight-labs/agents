#!/usr/bin/env python3
"""UserPromptSubmit: remind Claude to save durable facts after a long stretch without a watchthelight write.

Counts real prompts since the last `remember` call, resuming the transcript scan
from a stored byte offset so each prompt only reads what is new. Injects one line
every THRESHOLD prompts without a save; silent otherwise.
"""

import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

THRESHOLD = 8
WTL_DIR = os.path.join(H.STATE_DIR, "wtl")
SAVE_TOOL = re.compile(r"^mcp__.*__remember$")


def scan(path, state):
    try:
        with open(path, "rb") as f:
            f.seek(state["offset"])
            while True:
                raw = f.readline()
                if not raw or not raw.endswith(b"\n"):
                    break  # stop before a partly written last line
                state["offset"] = f.tell()
                if b'"timestamp"' not in raw:
                    continue
                try:
                    rec = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
                if rec.get("isSidechain"):
                    continue
                if H.is_real_prompt(rec):
                    state["since_save"] += 1
                elif rec.get("type") == "assistant":
                    for b in (rec.get("message") or {}).get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and SAVE_TOOL.match(str(b.get("name") or "")):
                            state["since_save"], state["nudged_at"] = 0, 0
    except OSError:
        pass


def main():
    data = H.read_input()
    sid, path = str(data.get("session_id") or ""), data.get("transcript_path") or ""
    if not sid or not path:
        return
    os.makedirs(WTL_DIR, exist_ok=True)
    state_path = os.path.join(WTL_DIR, f"nudge-{re.sub(r'[^A-Za-z0-9_-]', '', sid)[:64]}.json")
    state = {"offset": 0, "since_save": 0, "nudged_at": 0, **H.load_json(state_path, {})}
    scan(path, state)
    count = state["since_save"] + 1  # this prompt is not in the transcript yet
    message = ""
    if count >= THRESHOLD and count - state["nudged_at"] >= THRESHOLD:
        state["nudged_at"] = count
        message = (f"[memory] {count - 1} prompts since the last watchthelight save. If earlier work in this session "
                   "produced durable facts (decisions, fixes, gotchas, config or status changes, open loops), save them "
                   "with remember and echo the receipts; otherwise ignore this.")
    try:
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, state_path)
    except OSError:
        pass
    if message:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": message}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
