#!/usr/bin/env node
// caveman — Claude Code SessionStart activation hook
//
// Runs on every session start:
//   1. Writes "full" to flag file at ~/.claude/.caveman-active
//   2. Emits caveman ruleset as hidden SessionStart context
//
// Vendored from https://github.com/JuliusBrussee/caveman
// Adapted: auto-activate always, English only, no statusline nudge.

const fs = require('fs');
const path = require('path');
const os = require('os');

const claudeDir = path.join(os.homedir(), '.claude');
const flagPath = path.join(claudeDir, '.caveman-active');

// 1. Write flag file — auto-activate every session at "full"
try {
  fs.mkdirSync(path.dirname(flagPath), { recursive: true });
  fs.writeFileSync(flagPath, 'full');
} catch (e) {
  // Silent fail — flag is best-effort, don't block the hook
}

// 2. Emit caveman rules (always, English only)
const output =
  "CAVEMAN MODE ACTIVE (full). Rules: Drop articles/filler/pleasantries/hedging. " +
  "Fragments OK. Short synonyms. Pattern: [thing] [action] [reason]. [next step]. " +
  "Not: 'Sure! I'd be happy to help you with that.' " +
  "Yes: 'Bug in auth middleware. Fix:' " +
  "English only — never use wenyan or classical Chinese compression. " +
  "Max intensity: ultra-plus (文言文 thinking, minimal English output). " +
  "Code blocks/commits/security warnings: write normal. " +
  "User says 'normal' or 'stop caveman' to deactivate.";

process.stdout.write(output);
