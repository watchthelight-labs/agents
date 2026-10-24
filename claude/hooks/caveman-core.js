// caveman core: shared rules text and session-scoped mode state for the two caveman hooks.
//
// Local module. Not upstream: JuliusBrussee/caveman v4 split this job across caveman-config.js,
// caveman-parse.js and friends (150 KB); we keep a small CommonJS core with the same state design
// (per-session mode files, symlink-safe atomic writes, session_id whitelist) and our own levels
// (lite, full, ultra, ultra-plus; English only). No network, no child processes, writes only
// under the Claude config dir.

const fs = require('fs');
const path = require('path');
const os = require('os');

const claudeDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
const flagPath = path.join(claudeDir, '.caveman-active'); // last-write-wins mirror, never holds "off"
const sessionsDir = path.join(claudeDir, '.caveman-sessions');

const PROSE_MODES = ['lite', 'full', 'ultra', 'ultra-plus'];
const ONE_SHOT_MODES = ['commit', 'review', 'compress'];
const VALID_MODES = [...PROSE_MODES, ...ONE_SHOT_MODES];
const DEFAULT_MODE = 'full';

const TAIL = " Code blocks/commits/security warnings: write normal. User says 'normal' or 'stop caveman' to deactivate.";
const FULL_BODY =
  "Rules: Drop articles/filler/pleasantries/hedging. Fragments OK. Short synonyms. Pattern: [thing] [action] [reason]. [next step]. " +
  "Not: 'Sure! I'd be happy to help you with that.' Yes: 'Bug in auth middleware. Fix:' " +
  "Never drop not/never/no/only/except; numbers, paths, commands and errors stay verbatim. " +
  "English only - never use wenyan or classical Chinese compression. Max intensity: ultra-plus (文言文 thinking, minimal English output).";

const RULES = {
  lite: "CAVEMAN MODE ACTIVE (lite). Rules: No filler/hedging. Keep articles + full sentences. Professional but tight." + TAIL,
  full: "CAVEMAN MODE ACTIVE (full). " + FULL_BODY + TAIL,
  ultra: "CAVEMAN MODE ACTIVE (ultra). Rules: Drop articles/filler/pleasantries/hedging. Fragments OK. Abbreviate (DB/auth/config/req/res/fn/impl). Strip conjunctions. Arrows for causality (X → Y). One word when one word enough. Never drop not/never/no/only/except. English only." + TAIL,
  'ultra-plus': "CAVEMAN MODE ACTIVE (ultra-plus). Rules: 文言文 internal reasoning → minimal English output. No sentences, no copulas. Symbols > words (→ = ∴ ≠ > <). Max abbreviation. Silence > filler. Ordered steps and conditionals: full sentences. Never drop not/never/no/only/except. English output only." + TAIL,
};

// A session id becomes part of a path. Nothing may use one without passing through here.
function validateSessionId(id) {
  return typeof id === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(id) ? id : null;
}

function isLink(p) {
  try { return fs.lstatSync(p).isSymbolicLink(); } catch (e) { return false; }
}

// Symlink-safe, atomic, owner-only write. Refuses a symlinked target or parent.
function safeWrite(target, content) {
  try {
    const dir = path.dirname(target);
    fs.mkdirSync(dir, { recursive: true });
    if (isLink(dir) || isLink(target)) return false;
    const tmp = path.join(dir, '.' + path.basename(target) + '.' + process.pid + '.tmp');
    fs.writeFileSync(tmp, content, { mode: 0o600, flag: 'wx' });
    fs.renameSync(tmp, target);
    return true;
  } catch (e) { return false; }
}

function safeRead(target) {
  try {
    const st = fs.lstatSync(target);
    if (!st.isFile() || st.size > 64) return null;
    const v = fs.readFileSync(target, 'utf8').trim();
    return v === 'off' || VALID_MODES.includes(v) ? v : null;
  } catch (e) { return null; }
}

function sessionFile(sid, ext) {
  const id = validateSessionId(sid);
  return id ? path.join(sessionsDir, id + '.' + ext) : null;
}

// Literal stored value for this session ('off' included), else the legacy mirror, else null.
function readStored(sid) {
  const f = sessionFile(sid, 'mode');
  const own = f ? safeRead(f) : null;
  return own !== null ? own : safeRead(flagPath);
}

// Mode in effect: 'off' and nothing-stored both collapse to null.
function activeMode(sid) {
  const m = readStored(sid);
  return !m || m === 'off' ? null : m;
}

// Single writer. null or 'off' stores a durable 'off' for the session and removes the mirror.
function writeMode(sid, mode) {
  const f = sessionFile(sid, 'mode');
  const off = !mode || mode === 'off';
  if (!off && !VALID_MODES.includes(mode)) return;
  if (off) {
    if (f) safeWrite(f, 'off');
    try { if (!isLink(flagPath)) fs.unlinkSync(flagPath); } catch (e) {}
  } else {
    if (f) safeWrite(f, mode);
    safeWrite(flagPath, mode);
  }
}

// Prose mode displaced by a one-shot skill (commit/review/compress), restored on the next ordinary prompt.
function writePrev(sid, mode) {
  const f = sessionFile(sid, 'prev');
  if (f && PROSE_MODES.includes(mode)) safeWrite(f, mode);
}
function readPrev(sid) {
  const f = sessionFile(sid, 'prev');
  const m = f ? safeRead(f) : null;
  return PROSE_MODES.includes(m) ? m : null;
}

// Drop session files older than 14 days. Bounded; refuses symlinks.
function gcSessions(maxDeletes = 50) {
  try {
    const ttl = 14 * 24 * 3600 * 1000;
    let n = 0;
    for (const name of fs.readdirSync(sessionsDir)) {
      if (n >= maxDeletes) break;
      const p = path.join(sessionsDir, name);
      const st = fs.lstatSync(p);
      if (st.isFile() && Date.now() - st.mtimeMs > ttl) { fs.unlinkSync(p); n++; }
    }
  } catch (e) {}
}

// Read one hook payload from stdin. Resolves on the first complete JSON object (a host that holds
// the pipe open must not stall the hook), or after 2s with whatever arrived. Never rejects.
function readPayload(cb) {
  if (process.stdin.isTTY) return cb(null, false);
  let input = '';
  let done = false;
  const finish = (timedOut) => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    try { process.stdin.pause(); process.stdin.unref(); } catch (e) {}
    let data = null;
    try { data = JSON.parse(input); } catch (e) {}
    cb(data && typeof data === 'object' ? data : null, timedOut === true);
  };
  const timer = setTimeout(() => finish(true), 2000);
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (c) => {
    input += c;
    try { JSON.parse(input); } catch (e) { return; }
    finish();
  });
  process.stdin.on('error', () => finish());
  process.stdin.on('end', () => finish());
}

module.exports = {
  RULES, PROSE_MODES, ONE_SHOT_MODES, VALID_MODES, DEFAULT_MODE,
  validateSessionId, readStored, activeMode, writeMode, writePrev, readPrev, gcSessions, readPayload,
};
