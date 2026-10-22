#!/usr/bin/env node
// caveman — UserPromptSubmit hook to track which caveman mode is active
// Inspects user input for /caveman commands and writes mode to flag file.
// Also re-emits caveman rules on EVERY turn if mode is active, so rules
// survive context compression (the SessionStart injection gets dropped).
//
// Vendored from https://github.com/JuliusBrussee/caveman
// Adapted: wenyan commands mapped to "full" (English lock), no wenyan modes.

const fs = require('fs');
const path = require('path');
const os = require('os');

const flagPath = path.join(os.homedir(), '.claude', '.caveman-active');

const RULES = {
  lite: "CAVEMAN MODE ACTIVE (lite). Rules: No filler/hedging. Keep articles + full sentences. Professional but tight. Code blocks/commits/security warnings: write normal. User says 'normal' or 'stop caveman' to deactivate.",
  full: "CAVEMAN MODE ACTIVE (full). Rules: Drop articles/filler/pleasantries/hedging. Fragments OK. Short synonyms. Pattern: [thing] [action] [reason]. [next step]. Not: 'Sure! I'd be happy to help you with that.' Yes: 'Bug in auth middleware. Fix:' English only — never use wenyan or classical Chinese compression. Max intensity: ultra-plus (文言文 thinking, minimal English output). Code blocks/commits/security warnings: write normal. User says 'normal' or 'stop caveman' to deactivate.",
  ultra: "CAVEMAN MODE ACTIVE (ultra). Rules: Drop articles/filler/pleasantries/hedging. Fragments OK. Abbreviate (DB/auth/config/req/res/fn/impl). Strip conjunctions. Arrows for causality (X → Y). One word when one word enough. English only. Code blocks/commits/security warnings: write normal. User says 'normal' or 'stop caveman' to deactivate.",
  'ultra-plus': "CAVEMAN MODE ACTIVE (ultra-plus). Rules: 文言文 internal reasoning → minimal English output. No sentences, no copulas. Symbols > words (→ = ∴ ≠ > <). Max abbreviation. Silence > filler. English output only. Code blocks/commits/security warnings: write normal. User says 'normal' or 'stop caveman' to deactivate.",
};

let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  let deactivated = false;

  try {
    const data = JSON.parse(input);
    const prompt = (data.prompt || '').trim().toLowerCase();

    // Detect deactivation via natural language (check first so it takes priority)
    if (/\b(stop caveman|normal mode)\b/i.test(prompt)) {
      try { fs.unlinkSync(flagPath); } catch (e) {}
      deactivated = true;
    }

    // Match /caveman commands
    if (!deactivated && prompt.startsWith('/caveman')) {
      const parts = prompt.split(/\s+/);
      const cmd = parts[0];
      const arg = parts[1] || '';

      let mode = null;

      if (cmd === '/caveman-commit') {
        mode = 'commit';
      } else if (cmd === '/caveman-review') {
        mode = 'review';
      } else if (cmd === '/caveman-compress' || cmd === '/caveman:caveman-compress') {
        mode = 'compress';
      } else if (cmd === '/caveman' || cmd === '/caveman:caveman') {
        if (arg === 'lite') mode = 'lite';
        else if (arg === 'ultra-plus' || (arg === 'ultra' && parts[2] === 'plus')) mode = 'ultra-plus';
        else if (arg === 'ultra') mode = 'ultra';
        else if (arg === 'off') {
          // Deactivate
          try { fs.unlinkSync(flagPath); } catch (e) {}
          deactivated = true;
        }
        // English lock: wenyan requests map to full
        else if (arg.startsWith('wenyan')) mode = 'full';
        else mode = 'full';
      }

      if (mode) {
        fs.mkdirSync(path.dirname(flagPath), { recursive: true });
        fs.writeFileSync(flagPath, mode);
      }
    }
  } catch (e) {
    // Silent fail on parse errors
  }

  // Re-emit caveman rules if mode is active (survives context compression)
  if (!deactivated) {
    try {
      const mode = fs.readFileSync(flagPath, 'utf8').trim();
      // Only emit rules for communication modes (not commit/review/compress sub-skills)
      if (RULES[mode]) {
        process.stdout.write(RULES[mode]);
      }
    } catch (e) {
      // Flag file doesn't exist — caveman not active, emit nothing
    }
  }
});
