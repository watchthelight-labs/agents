<!-- <wtl> project: agents | file: docs/hooks.md | author: watchthelight </wtl> -->
# Hooks

All in [claude/hooks/](../claude/hooks), wired by [settings.template.json](../claude/settings.template.json). Every Python hook reads one JSON object on stdin and never raises: a hook bug must never block a session (`cchooks.py` has the shared plumbing).

| When | Hook | What it does |
|---|---|---|
| Session start | `caveman-activate.js` | Turns on caveman mode (see [methods/caveman.md](methods/caveman.md)) |
| Session start | `wtl_boot.py profile / infra / project / threads` | Four parallel hooks, each under Claude Code's 10,000-character hook limit, so together about 36k characters of memory reach the session. Each part is cached per folder and shown with a banner when the server is down |
| Session start (after compaction / resume) | `compact_guard.py` | Prints back what was saved before the compaction |
| Every prompt | `caveman-mode-tracker.js` | Follows `/caveman lite\|full\|ultra` and repeats the rules each turn |
| Every prompt | `quota_advisory.py` | One line when the 5-hour or weekly window is close to empty, so Claude itself fans out fewer agents |
| Every prompt | `wtl_nudge.py` | After eight prompts without a memory write, reminds Claude to save what's durable |
| Before Bash, PowerShell, Write, Edit | `guardrails.py` | Rules from [guardrails.json](../claude/guardrails.json). A match answers *deny* (Claude has to ask me in chat) or *ask* (permission prompt). Examples: no recursive deletes outside the scratchpad, no registry deletes (a keyboard remap lives there), no force pushes, no restarting a game server people may be on, settings edits always ask |
| After every command or file write | `audit.py` | One row per command or write in `~/.claude/cmdlog.jsonl`: when, where, what, how long, success, error. `/cmdlog` queries it |
| Before compaction | `compact_guard.py` | Saves what summaries tend to lose: the last prompts verbatim, standing constraints, files touched, background jobs |
| End of turn | `turn_end.py` | A receipt per turn in `~/.claude/ledger.jsonl` (tokens by model, agents), `/quota` reports over it. Long turns and turns with agents send a toast and an ntfy ping |
| Claude needs input | `turn_end.py` | "Claude needs you" on the desktop and the phone |

The **status line** ([statusline.py](../claude/statusline/statusline.py)) shows the model, context use, and the 5-hour and weekly quota with a burn rate. The quota hooks reuse its numbers.
