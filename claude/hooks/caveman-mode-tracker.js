#!/usr/bin/env node
// caveman - UserPromptSubmit hook to track which caveman mode is active
// Inspects user input for /caveman commands and plain-language on/off phrases, stores the mode for
// THIS session, and re-emits the active ruleset on EVERY turn so it survives context compression
// and competing instructions.
//
// Vendored from https://github.com/JuliusBrussee/caveman (state design from v4.0.1).
// Adapted: wenyan requests map to "full" (English lock), extra level "ultra-plus", no stats command,
// no repo/user config lookup. Shared code lives in caveman-core.js.

const core = require('./caveman-core');

const STOP = /\b(stop caveman|normal mode|disable caveman|deactivate caveman|caveman off)\b/;
const START = /\b(activate caveman|turn on caveman|enable caveman|start caveman|caveman mode on|talk like (a )?caveman)\b/;
const MAX_PHRASE_WORDS = 8; // a long prompt that merely mentions the phrase is not a command

// Slash skills may reach the hook wrapped as <command-name>/x</command-name><command-args>y</command-args>.
function unwrapCommand(prompt) {
  const name = /<command-name>\s*([^<\s]+)\s*<\/command-name>/.exec(prompt);
  if (!name) return prompt;
  const args = /<command-args>\s*([^<]*?)\s*<\/command-args>/.exec(prompt);
  return (name[1].startsWith('/') ? name[1] : '/' + name[1]) + (args && args[1] ? ' ' + args[1] : '');
}

core.readPayload((data) => {
  try {
    if (!data) return;
    const sid = core.validateSessionId(data.session_id);
    const prompt = unwrapCommand(String(data.prompt || data.user_prompt || '')).trim().toLowerCase();
    const words = prompt.split(/\s+/).filter(Boolean).length;
    let stored = core.readStored(sid);
    let oneShotCommand = false;

    if (words <= MAX_PHRASE_WORDS && STOP.test(prompt)) {
      core.writeMode(sid, 'off');
    } else if (prompt.startsWith('/caveman')) {
      const parts = prompt.split(/\s+/);
      const cmd = parts[0];
      const arg = parts[1] || '';
      let mode = null;

      if (cmd === '/caveman-commit' || cmd === '/caveman:caveman-commit') mode = 'commit';
      else if (cmd === '/caveman-review' || cmd === '/caveman:caveman-review') mode = 'review';
      else if (cmd === '/caveman-compress' || cmd === '/caveman:caveman-compress') mode = 'compress';
      else if (cmd === '/caveman' || cmd === '/caveman:caveman') {
        if (arg === 'status') {
          // Read-only: report, change nothing, skip the ruleset.
          process.stdout.write('Caveman mode: ' + (core.activeMode(sid) || 'off'));
          return;
        }
        if (arg === 'off') { core.writeMode(sid, 'off'); stored = 'off'; }
        else if (arg === 'lite') mode = 'lite';
        else if (arg === 'ultra-plus' || (arg === 'ultra' && parts[2] === 'plus')) mode = 'ultra-plus';
        else if (arg === 'ultra') mode = 'ultra';
        else mode = 'full'; // includes wenyan*: English lock
      }

      if (mode) {
        if (core.ONE_SHOT_MODES.includes(mode)) {
          oneShotCommand = true;
          if (core.PROSE_MODES.includes(stored)) core.writePrev(sid, stored); // remember what to return to
        }
        core.writeMode(sid, mode);
      }
    } else if ((!stored || stored === 'off') && words <= MAX_PHRASE_WORDS && START.test(prompt)) {
      core.writeMode(sid, core.DEFAULT_MODE);
    }

    // A one-shot skill (commit/review/compress) lasts one prompt; the next ordinary prompt restores
    // the prose mode it displaced.
    stored = core.readStored(sid);
    if (!oneShotCommand && core.ONE_SHOT_MODES.includes(stored)) {
      core.writeMode(sid, core.readPrev(sid) || core.DEFAULT_MODE);
    }

    const mode = core.activeMode(sid);
    if (mode && core.RULES[mode]) process.stdout.write(core.RULES[mode]);
  } catch (e) {
    // Silent fail on parse errors
  }
});
