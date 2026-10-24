#!/usr/bin/env node
// caveman - Claude Code SessionStart activation hook
//
// Runs on every SessionStart (source: startup, resume, clear, compact, fork):
//   1. startup/clear: auto-activate at "full" for THIS session. Anything else (compact, resume,
//      fork, unknown) keeps the mode the session already has, so a mid-session "ultra-plus" or an
//      explicit "stop caveman" survives auto-compaction.
//   2. Emit the active mode's ruleset as hidden SessionStart context (compaction prunes it, so it
//      is re-emitted on every source). A session that stored "off" gets nothing.
//
// Vendored from https://github.com/JuliusBrussee/caveman (state design from v4.0.1).
// Adapted: auto-activate always, English only, levels lite/full/ultra/ultra-plus, no statusline nudge,
// no repo/user config lookup, no subagent or session-end hooks. Shared code lives in caveman-core.js.

const core = require('./caveman-core');

const RESET_SOURCES = new Set(['startup', 'clear']);

core.readPayload((data, timedOut) => {
  try {
    const source = !timedOut && data && typeof data.source === 'string' ? data.source : (timedOut ? 'unknown' : 'startup');
    const sid = core.validateSessionId(data && data.session_id);

    let mode;
    if (RESET_SOURCES.has(source)) {
      mode = core.DEFAULT_MODE;
      core.writeMode(sid, mode);
      if (source === 'startup') core.gcSessions();
    } else {
      const stored = core.readStored(sid);
      if (stored === 'off') return;                      // user turned it off; stay off
      mode = stored || core.DEFAULT_MODE;                // nothing stored: fresh default
      if (!stored) core.writeMode(sid, mode);
      if (!core.RULES[mode]) mode = core.readPrev(sid) || core.DEFAULT_MODE; // one-shot mid-flight
    }
    process.stdout.write(core.RULES[mode]);
  } catch (e) {
    // Silent fail: a hook must never block session start.
  }
});
