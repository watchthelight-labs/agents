#!/usr/bin/env python3
"""PostToolUse (Bash): after a command that posts on GitHub, remind Claude to log the conversation with log_contact.

Silent for everything else. The server also finds threads we are in through its involves: search, so this is the
first of two backstops, not the only record.
"""

import json, re, sys

POST = re.compile(r"\bgh\s+(issue|pr)\s+(comment|create|review)\b|\bgh\s+api\b.*(comments|/issues|/pulls|/reviews)"
                  r".*(-X\s*POST|--method\s+POST|-f\s+body=|-F\s+body=|--field\s+body=)", re.S)
URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull|discussions)/\d+(?:#[\w-]+)?")


def main():
    data = json.load(sys.stdin)
    command = str((data.get("tool_input") or {}).get("command") or "")
    if not POST.search(command):
        return
    resp = data.get("tool_response")
    text = json.dumps(resp) if not isinstance(resp, str) else resp
    urls = sorted(set(URL.findall(text)))[:5]
    where = (" Links in the output: " + ", ".join(urls) + ".") if urls else ""
    message = ("[contacts] That command posted on GitHub. Call log_contact with the comment or issue url, who you "
               "talked to, why we are there and our stance, then echo the receipt." + where)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
