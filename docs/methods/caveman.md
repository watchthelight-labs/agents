<!-- <wtl> project: agents | file: docs/methods/caveman.md | author: watchthelight </wtl> -->
# Caveman

Agents talk to me tersely by default: no greetings, no restating the question, no hedging, fragments are fine. It cuts reply tokens by roughly three quarters and, more to the point, I read faster. The skill and its two hooks come from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (Apache-2.0 / MIT); my copies are in [claude/skills/caveman](../../claude/skills/caveman) and [claude/hooks](../../claude/hooks).

| Level | Example |
|---|---|
| lite | "Your component re-renders because you create a new object reference each render. Wrap it in `useMemo`." |
| full (my default) | "New object ref each render → re-render. Wrap in `useMemo`." |
| ultra | "Inline obj prop → new ref → re-render. `useMemo`." |

Switch with `/caveman lite|full|ultra`, or say "normal" to turn it off.

**What stays normal, always:**
- code, commands and commit messages;
- security warnings and anything about data loss;
- text that leaves the session: READMEs, issue comments, release notes. That goes through the humanize rules instead: clear, human, no em dashes;
- teaching. When I'm learning something (studying, a new codebase) the agent switches to a patient mentor voice and walks through it step by step.

The companion skills: `caveman-commit` (short conventional commits), `caveman-review` (one-line review comments with exact line references), `caveman-compress` (rewrites memory files like `CLAUDE.md` in caveman form to save input tokens, keeping a readable backup).
