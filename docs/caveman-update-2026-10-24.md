# caveman update, 2026-10-24

Upstream: JuliusBrussee/caveman, pinned at tag v4.0.1 (d262ab3882952a59312ff3537cd86d894523c5ab, 2026-10-13, latest release tag; main was 1f951fb, a day old, not used).
Previous base: no commit was recorded. Our copy matched upstream around 2026-04-09 (a9e62b48, "Add mode-tracker hook"), then diverged by local rewrite.

## What upstream became

A monorepo (Go engine, proxy, browse, CLI, 30+ agent installer). The Claude hooks are now six files, about 150 KB (`src/hooks/`), with per-session mode state, repo/user config files, a SubagentStart hook, a SessionEnd stats recorder (spawns child processes) and a statusline. Levels were replaced by three skills: caveman (lite/full), ultracave (ultra) and megacave (wenyan). The caveman skill was rewritten (nine rules, answer first, bounded tool status, no arrows, no invented abbreviations).

## Decision

Full adoption would mean re-grafting `ultra-plus` and the English lock onto a 150 KB state machine we do not otherwise need. We kept our small hooks and ported the upstream behaviour that matters:

- SessionStart no longer resets the mode on compact/resume/fork (upstream #691): a mid-session ultra-plus or an explicit "stop caveman" survives compaction. startup and clear still auto-activate at full.
- Mode is per session (`~/.claude/.caveman-sessions/<session_id>.mode`), `.caveman-active` stays as a last-write-wins mirror that never holds "off". session_id is whitelisted before it touches a path.
- Symlink-safe atomic writes (O_EXCL temp + rename, refuses symlinked file or parent), as upstream `safeWriteFlag`.
- Stdin read returns on the first complete JSON object with a 2s watchdog (upstream #729/#833, Windows pipe lag).
- One-shot skills (commit/review/compress) restore the displaced prose mode on the next prompt.
- `/caveman status` (read-only), `/caveman off`, `<command-name>` envelope handling, natural-language on/off phrases (short prompts only, so a long prompt that merely mentions "stop caveman" is not a command).
- Skill text: caveman SKILL.md gains the v4 rules (never drop negations, bounded tool-run status, never perform caveman, persisted-outside-chat and question exemptions, pre-send check). caveman-commit gets the user-attribution-trailer clause. caveman-compress gets the explicit-filepath rule, secret-file refusal and wider type lists.

## Kept local

- `ultra-plus` level and its hook text; English only, no wenyan/megacave; levels lite/full/ultra/ultra-plus kept (upstream removed `lite` as a separate level).
- Auto-activate every session. No statusline nudge.
- caveman-compress stays in-session (no `scripts/`): upstream's script sends the file to a model provider.
- Not taken: caveman-config/parse/stats/statusline/host-session-start, SubagentStart and SessionEnd hooks, cavecrew, and the engine/proxy/browse/mem skills.

## Security review (files taken or read)

Read: README and CLAUDE.md of upstream, `src/hooks/caveman-activate.js` (stdin/state/emit path), grep of all four hook files for require/network/exec. Taken code is our own (`caveman-core.js`, activate, tracker): only `fs`, `path`, `os`; no network, no child_process, no telemetry; writes only under `$CLAUDE_CONFIG_DIR` (default `~/.claude`). Upstream's tracker requires `child_process` (stats command) and its compress scripts call model providers; neither was taken. The remaining upstream hook files (config, parse, stats, 150 KB) were not read line by line because they are not installed.
