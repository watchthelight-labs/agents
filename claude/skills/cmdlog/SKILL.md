---
name: cmdlog
description: >
  Query the local audit trail of every shell command and file write Claude Code
  ran on this machine (~/.claude/cmdlog.jsonl, written by the PostToolUse hook),
  including guardrail denials. Trigger: /cmdlog [filters]. Use when the user asks
  what commands ran, which files were changed, what failed, or when a session did
  something.
user_invocable: true
arg_description: "[--since 2h|3d|YYYY-MM-DD] [--grep RE] [--tool Bash] [--session PFX] [--failed] [--files] [--guardrails] [--bg] [-n N] [--summary]"
---

Run exactly:

```
PYTHONIOENCODING=utf-8 python ~/.claude/hooks/cmdlog.py $ARGUMENTS
```

Default window is the last day. Show the output verbatim in a code block. Add
at most one line of interpretation, and only if the user asked a question the
table does not answer by itself.
