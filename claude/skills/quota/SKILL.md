---
name: quota
description: >
  Explain where the Claude usage quota went: per-turn ledger (~/.claude/ledger.jsonl,
  written by the Stop hook) aggregated by project, model, hour, session or day for
  the current weekly or 5-hour window, with the costliest turns. Trigger: /quota
  [options]. Use when the user asks why the weekly/5h meter is high, which project
  or agents ate the quota, or for a usage report.
user_invocable: true
arg_description: "[--window wk|5h|all|12h|3d] [--by project|model|hour|session|day] [--top N]"
---

Run exactly:

```
PYTHONIOENCODING=utf-8 python ~/.claude/hooks/quota.py $ARGUMENTS
```

Show the output verbatim in a code block. The share column is an estimate that
blends models; say so only if the user asks how it is computed. If the ledger is
empty, say the Stop hook only records turns finished after it was installed.
