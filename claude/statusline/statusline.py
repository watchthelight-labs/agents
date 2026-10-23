#!/usr/bin/env python3
"""Claude Code Status Line -- model, context (+autocompact mark), rate limits with
burn rate, Fable weekly, session tokens incl. subagents, working time.

`statusline.py --refresh-usage` is the detached worker that polls the usage
endpoint; the render path never touches the network."""

import json, sys, time, os, tempfile, re, shutil, subprocess, urllib.request

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"; BLINK = "\033[5m"
RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; CYAN = "\033[36m"
MAGENTA = "\033[35m"; BLUE = "\033[34m"; WHITE = "\033[37m"
I_DIA = "◆"
SEP = f" {DIM}│{RESET} "

# claude-opus-5-5[1m], claude-sonnet-5, claude-fable-5-1, claude-haiku-4-5-20251001,
# claude-3-5-sonnet-20241022, claude-3-opus-20240229 -> "Opus 5.5", "Sonnet 5", ...
MODEL_RE = re.compile(
    r"^claude-(?:(\d+)(?:-(\d+))?-)?(opus|sonnet|haiku|fable)"
    r"(?:-(\d+)(?:-(\d+))?)?(?:-\d{8})?(\[1m\])?$")


def model_label(model_id, display_name="", ctx_size=0):
    """(short name, is_1m, matched). Falls back to display_name / raw id."""
    m = MODEL_RE.match(model_id or "")
    if m:
        maj = m.group(1) or m.group(4)
        mnr = m.group(2) or m.group(5)
        name = m.group(3).capitalize()
        if maj:
            name += f" {maj}" + (f".{mnr}" if mnr else "")
        one_m = bool(m.group(6)) or ctx_size >= 900_000
        return name, one_m, True
    short = display_name or model_id or ""
    if short.lower().startswith("claude "):
        short = short[7:]
    return short, ctx_size >= 900_000, False

EFFORT_COLOR = {
    "low":    DIM + GREEN,
    "medium": GREEN,
    "high":   YELLOW,
    "xhigh":  MAGENTA,
    "max":    RED + BOLD,
}

VIM_COLOR = {
    "INSERT":      GREEN,
    "NORMAL":      CYAN,
    "VISUAL":      YELLOW,
    "VISUAL LINE": MAGENTA,
}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def vlen(s):
    """Visible width: code-point count after stripping ANSI SGR codes."""
    return len(ANSI_RE.sub("", s))


def vtrunc(s, w):
    """Truncate to visible width w (with ellipsis), preserving ANSI codes."""
    if vlen(s) <= w:
        return s
    if w <= 1:
        return RESET
    out, vis = [], 0
    for m in re.finditer(r"(\x1b\[[0-9;]*m)|(.)", s, re.S):
        if m.group(1):
            out.append(m.group(1))
        else:
            if vis >= w - 1:
                break
            out.append(m.group(2)); vis += 1
    out.append("…" + RESET)
    return "".join(out)


def term_cols():
    """Current terminal width. Claude Code exports COLUMNS (v2.1.153+);
    fall back to shutil for older versions / odd environments."""
    try:
        c = int(os.environ.get("COLUMNS") or 0)
    except ValueError:
        c = 0
    if c <= 0:
        c = shutil.get_terminal_size((100, 20)).columns
    return c


def fit_line(items, avail, sep):
    """Render items to fit `avail` visible columns.

    items: list of dicts {"text", "prio", "compact"?}. Higher prio = dropped
    sooner; prio 0 is never dropped. Strategy: full -> swap to compact forms
    (high-prio first) -> drop droppable segments -> hard-truncate essentials.
    """
    if not items:
        return ""
    sepv = vlen(sep)
    active = list(range(len(items)))
    compact = set()

    def part(i):
        it = items[i]
        return it["compact"] if (i in compact and it.get("compact")) else it["text"]

    def width():
        return sum(vlen(part(i)) for i in active) + sepv * max(0, len(active) - 1)

    if width() > avail:
        for i in sorted(range(len(items)), key=lambda i: -items[i]["prio"]):
            if items[i].get("compact"):
                compact.add(i)
                if width() <= avail:
                    break

    if width() > avail:
        for i in sorted([j for j in active if items[j]["prio"] > 0],
                        key=lambda j: -items[j]["prio"]):
            active.remove(i)
            if width() <= avail:
                break

    line = sep.join(part(i) for i in active)
    return vtrunc(line, avail)


def cbar(pct, w=20, mark=None):
    """Bar of width w. `mark` (0..1) draws a tick in the unfilled part, e.g.
    where autocompact fires."""
    bk = " ▏▎▍▌▋▊▉█"
    fl = pct * w / 100.0; fu = int(fl); fr = fl - fu; pi = int(fr * (len(bk) - 1))
    mi = int(mark * w) if mark is not None and 0 < mark < 1 else -1
    b = ""
    for i in range(w):
        if i < fu: b += "█"
        elif i == fu: b += bk[pi] if i != mi or pi else "╎"
        elif i == mi: b += "╎"
        else: b += "░"
    c = RED + BOLD if pct >= 90 else YELLOW if pct >= 75 else CYAN if pct >= 50 else GREEN
    return f"{c}{b}{RESET}"


METER_LABEL = BOLD + WHITE   # one readable color for every row label
METER_LW = 5                 # widest label ("fable"); shorter ones pad out to it


def meter_lines(meters, avail, lw=METER_LW):
    """One stacked row per usage window: label, bar, percentage, note.

    meters: (label, pct, note[, mark[, pct_color]]). `note` is a pre-colored
    trailing string (reset time, burn rate, absolute tokens). `mark` is a 0..1
    bar tick. `pct_color` overrides the 75/90 percent coloring.
    """
    out = []
    # leading space + "* " + label + bar + " 100.0%" -> the rest is the bar
    bw = max(6, min(20, avail - lw - 11))
    for m in meters:
        label, pct, note = m[0], float(m[1] or 0), m[2]
        mark = m[3] if len(m) > 3 else None
        pc = m[4] if len(m) > 4 and m[4] is not None else (
            RED + BOLD if pct >= 90 else YELLOW if pct >= 75 else "")
        row = (f" {METER_LABEL}{I_DIA} {label:<{lw}}{RESET} "
               f"{cbar(pct, bw, mark)} {pc}{fpct(pct):>6}{RESET}")
        if note:
            row += f"  {note}"
        out.append(vtrunc(row, avail))
    return out


def fmt_reset_5h(epoch):
    secs = max(0, epoch - time.time())
    if secs <= 0: return ""
    h = int(secs // 3600); m = int((secs % 3600) // 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def fmt_reset_7d(epoch):
    if epoch <= 0: return ""
    try:
        t = time.localtime(epoch)
        day = time.strftime("%a", t)
        hour = t.tm_hour % 12 or 12
        ampm = "am" if t.tm_hour < 12 else "pm"
        return f"{day} {hour}:{t.tm_min:02d}{ampm}"
    except (OSError, ValueError):
        return ""


def fmt_dur(secs):
    """Compact duration: 1h04m / 12m34s / 41s."""
    secs = int(max(0, secs))
    h, m, sec = secs // 3600, (secs % 3600) // 60, secs % 60
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def _tstamp(s):
    """ISO-8601 transcript timestamp -> float epoch (0 on failure)."""
    if not s:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return 0.0


def fpct(p):
    return f"{float(p or 0):.1f}%"


def humanize(n):
    n = int(n or 0)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)


USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens", "output_tokens")


def _file_acc():
    """Per-transcript-file token state (main thread or one agent)."""
    return {"_offset": 0, "fresh": 0, "cache_read": 0, "down": 0,
            "pend_id": "", "pend": None, "last_up": 0, "last_down": 0,
            "ttl": 0, "last_ts": 0.0, "model": ""}


def _turn_state():
    """Main-thread state: working time, open turn, context attribution."""
    return {"work_total": 0.0, "last_turn": 0.0,
            "turn_start": 0.0, "turn_last": 0.0, "turn_open": 0,
            "turn_offset": 0, "turn_ctx0": 0, "t0_main": [0, 0, 0],
            "ctx_hist": [], "prev_in": 0, "pending": [], "attr": {}, "hog": None,
            "open_tools": {}, "compactions": 0, "compact_pending": 0,
            "last_compact": None}


def _commit(fa):
    p = fa.get("pend")
    if p:
        fa["fresh"] += p[0] + p[1]
        fa["cache_read"] += p[2]
        fa["down"] += p[3]
    fa["pend"] = None
    fa["pend_id"] = ""


def _take_usage(fa, msg, ts=0.0):
    """Fold one assistant record's usage into fa, deduping by message id.

    One API message is written as several transcript records (one per
    content block), each carrying the same usage dict. Only the last record
    for a given message id counts; fields are max-merged in case an early
    record lacks output_tokens. Also notes the prompt-cache TTL in use
    (1h vs 5m), the record time and the model.
    """
    usage = msg.get("usage")
    if not usage:
        return
    u = [int(usage.get(k, 0) or 0) for k in USAGE_KEYS]
    mid = msg.get("id") or ""
    if mid and mid == fa["pend_id"] and fa["pend"]:
        fa["pend"] = [max(a, b) for a, b in zip(fa["pend"], u)]
    else:
        _commit(fa)
        fa["pend_id"] = mid
        fa["pend"] = u
    p = fa["pend"]
    fa["last_up"] = p[0] + p[1] + p[2]
    fa["last_down"] = p[3]
    cc = usage.get("cache_creation") or {}
    if cc.get("ephemeral_1h_input_tokens"):
        fa["ttl"] = 3600
    elif cc.get("ephemeral_5m_input_tokens"):
        fa["ttl"] = 300
    if ts:
        fa["last_ts"] = max(float(fa.get("last_ts") or 0.0), ts)
    mdl = msg.get("model") or ""
    if mdl and not mdl.startswith("<"):   # "<synthetic>" = Claude Code placeholder
        fa["model"] = mdl


def _file_totals(fa):
    p = fa.get("pend") or [0, 0, 0, 0]
    return (fa["fresh"] + p[0] + p[1], fa["cache_read"] + p[2], fa["down"] + p[3])


def _tool_summary(name, inp):
    """Short label for a tool call: command head, file basename, agent job."""
    if not isinstance(inp, dict):
        return ""
    if name in ("Bash", "PowerShell"):
        s = " ".join(str(inp.get("command") or "").split())
    elif name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        s = os.path.basename(str(inp.get("file_path") or inp.get("notebook_path") or ""))
    elif name == "Agent":
        s = str(inp.get("description") or inp.get("subagent_type") or "")
    elif name in ("Grep", "Glob"):
        s = str(inp.get("pattern") or "")
    elif name == "Skill":
        s = str(inp.get("skill") or "")
    elif name == "WebFetch":
        s = str(inp.get("url") or "")
    elif name == "ToolSearch":
        s = str(inp.get("query") or "")
    else:
        s = ""
    return s[:40]


def _content_len(c):
    """Rough size in chars of a message/tool_result content (images ~1.5K tok)."""
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        n = 0
        for b in c:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                n += len(b.get("text") or "")
            elif t == "image":
                n += 6000
            else:
                n += len(json.dumps(b))
        return n
    return len(json.dumps(c)) if c else 0


def _attribute(turns, fa, msg):
    """Charge a new API message's context growth to what arrived since the
    previous one: tool results and your prompt (split by size) and Claude's
    own previous output. Exact in total, proportional within a turn."""
    usage = msg.get("usage") or {}
    total_in = sum(int(usage.get(k, 0) or 0) for k in USAGE_KEYS[:3])
    if not total_in:
        return
    attr = turns["attr"]
    pending = turns["pending"]
    if turns["prev_in"] == 0 and not turns["compact_pending"]:
        # first call: system prompt, CLAUDE.md, tool schemas, first prompt
        attr["system"] = attr.get("system", 0) + total_in
        turns["pending"] = []
        turns["prev_in"] = total_in
        return
    if turns["compact_pending"]:
        delta, prev_out = total_in, 0
        turns["compact_pending"] = 0
        if turns["turn_ctx0"] < 0:
            turns["turn_ctx0"] = total_in  # re-seed the growth baseline
    else:
        delta = max(0, total_in - turns["prev_in"])
        prev_out = int(fa.get("last_down") or 0)
    claude = min(delta, prev_out)
    if claude:
        attr["claude"] = attr.get("claude", 0) + claude
    rest = delta - claude
    if rest > 0:
        if not pending:
            attr["other"] = attr.get("other", 0) + rest
        else:
            chars = sum(max(1, p[2]) for p in pending)
            for cat, summ, ch in pending:
                tok = int(rest * max(1, ch) / chars)
                if tok <= 0:
                    continue
                attr[cat] = attr.get(cat, 0) + tok
                hog = turns.get("hog")
                if cat not in ("you", "system", "summary") and (not hog or tok > hog[1]):
                    turns["hog"] = [f"{cat} {summ}".strip()[:36], tok]
    turns["pending"] = []
    turns["prev_in"] = total_in


def _scan(path, fa, turns=None):
    """Read new records of one transcript file into fa (tokens) and, when
    `turns` is given, the main-thread state: working time, open turn, open
    tool calls, context attribution, compactions. Binary read so each
    record's byte offset is known (tell() is illegal mid-iteration)."""
    with open(path, "rb") as f:
        f.seek(fa["_offset"])
        pos = fa["_offset"]
        for raw in f:
            start = pos
            pos += len(raw)
            line = raw.decode("utf-8", "replace").strip()
            if not line or ('"usage"' not in line and '"timestamp"' not in line):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            rtype = rec.get("type")
            msg = rec.get("message") or {}
            ts = _tstamp(rec.get("timestamp"))

            if turns is not None and not rec.get("isSidechain"):
                acc = turns
                if rtype == "system" and rec.get("subtype") == "compact_boundary":
                    acc["compactions"] += 1
                    acc["compact_pending"] = 1
                    acc["turn_ctx0"] = -1  # growth baseline unknown until the next call
                    acc["attr"] = {}
                    acc["hog"] = None
                    acc["open_tools"] = {}
                    acc["pending"] = []
                    cm = rec.get("compactMetadata") or {}
                    acc["last_compact"] = [ts, cm.get("preTokens"), cm.get("postTokens")]
                if rtype == "user":
                    content = msg.get("content")
                    results = ([b for b in content if isinstance(b, dict)
                                and b.get("type") == "tool_result"]
                               if isinstance(content, list) else [])
                    if rec.get("isCompactSummary"):
                        acc["pending"].append(["summary", "", _content_len(content)])
                    elif not rec.get("isMeta") and ts and (
                            isinstance(content, str)
                            or (isinstance(content, list) and not results)):
                        # A real user prompt opens a turn (tool results are type "user" too).
                        span = acc["turn_last"] - acc["turn_start"]
                        if acc["turn_start"] and span > 0:
                            acc["work_total"] += span
                            acc["last_turn"] = span
                        # per-turn context growth; the first turn (system prompt) and
                        # any turn straddling a compaction are excluded
                        if acc["turn_ctx0"] > 0 and acc["prev_in"] > acc["turn_ctx0"]:
                            acc["ctx_hist"] = (acc["ctx_hist"]
                                               + [acc["prev_in"] - acc["turn_ctx0"]])[-8:]
                        if acc["turn_ctx0"] >= 0:
                            acc["turn_ctx0"] = acc["prev_in"]
                        acc["turn_start"] = ts
                        acc["turn_last"] = ts
                        acc["turn_open"] = 1
                        acc["turn_offset"] = start
                        acc["t0_main"] = list(_file_totals(fa))
                        acc["open_tools"] = {}
                        acc["pending"].append(["you", "", _content_len(content)])
                    for b in results:
                        info = acc["open_tools"].pop(b.get("tool_use_id"), None)
                        name, summ = (info[0], info[1]) if info else ("tool", "")
                        acc["pending"].append([name, summ, _content_len(b.get("content"))])
                if ts and acc["turn_start"]:
                    acc["turn_last"] = max(acc["turn_last"], ts)
                if rtype == "assistant":
                    mid = msg.get("id") or ""
                    if mid and mid != fa["pend_id"]:
                        _attribute(acc, fa, msg)
                    for b in msg.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id"):
                            acc["open_tools"][b["id"]] = [
                                b.get("name") or "tool",
                                _tool_summary(b.get("name"), b.get("input")), ts]
                    # "tool_use" -> more work coming; "end_turn" & friends -> turn done
                    stop = msg.get("stop_reason")
                    if stop:
                        acc["turn_open"] = 1 if stop == "tool_use" else 0

            if rtype == "assistant":
                _take_usage(fa, msg, ts)
        fa["_offset"] = pos


SIDECAR_V = 5


def parse_usage(transcript_path):
    """Sum token usage across the transcript AND its subagent transcripts
    (<dir>/<session>/subagents/agent-*.jsonl: Agent tool, forks, workflows),
    with an incremental sidecar cache per file.

    Also measures "working time": wall clock from each real user prompt to the
    last transcript record of that turn (tool results and all).

    Returns dict: fresh, cache_read, down (totals incl. agents), last_up,
    last_down (main thread), agent_fresh, agent_cache_read, agent_down,
    agent_n, work_total, last_turn, ttl, last_ts, model, turns (the
    main-thread state dict)  (or None on failure).
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return None

    sess = os.path.splitext(os.path.basename(transcript_path))[0]
    cache_path = os.path.join(tempfile.gettempdir(), f"clstatus-{sess}.json")
    agent_dir = os.path.join(os.path.dirname(transcript_path), sess, "subagents")

    turns = _turn_state()
    main = _file_acc()
    agents = {}

    # Resume from cache if the main file only grew (same inode-ish: size >= cached).
    try:
        with open(cache_path, "r", encoding="utf-8") as cf:
            cached = json.load(cf)
        cm = cached.get("main") or {}
        if (isinstance(cached, dict) and cached.get("_v") == SIDECAR_V
                and 0 < cm.get("_offset", 0) <= size):
            main.update({k: cm[k] for k in main if k in cm})
            ct = cached.get("turns") or {}
            turns.update({k: ct[k] for k in turns if k in ct})
            for name, fa in (cached.get("agents") or {}).items():
                a = _file_acc(); a.update({k: fa[k] for k in a if k in fa})
                agents[name] = a
    except (OSError, ValueError, AttributeError):
        pass

    try:
        _scan(transcript_path, main, turns)
    except OSError:
        return None

    # Subagent transcripts: each file keeps its own offset; untouched files
    # (size == offset) are not reopened.
    try:
        with os.scandir(agent_dir) as it:
            for de in it:
                if not (de.name.startswith("agent-") and de.name.endswith(".jsonl")):
                    continue
                try:
                    asz = de.stat().st_size
                except OSError:
                    continue
                fa = agents.get(de.name)
                if fa is None or fa["_offset"] > asz:
                    fa = agents[de.name] = _file_acc()
                if asz == fa["_offset"]:
                    continue
                try:
                    _scan(de.path, fa)
                except OSError:
                    pass
    except OSError:
        pass

    # Atomic write: hooks (turn_end.py) call parse_usage too.
    try:
        tmp = f"{cache_path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as cf:
            json.dump({"_v": SIDECAR_V, "main": main, "turns": turns, "agents": agents}, cf)
        os.replace(tmp, cache_path)
    except OSError:
        pass

    mf, mc, md = _file_totals(main)
    af = ac = ad = 0
    for fa in agents.values():
        f_, c_, d_ = _file_totals(fa)
        af += f_; ac += c_; ad += d_
    acc = {"fresh": mf + af, "cache_read": mc + ac, "down": md + ad,
           "last_up": main["last_up"], "last_down": main["last_down"],
           "agent_fresh": af, "agent_cache_read": ac, "agent_down": ad,
           "agent_n": len(agents),
           "work_total": turns["work_total"], "last_turn": turns["last_turn"],
           "ttl": main.get("ttl") or 0, "last_ts": main.get("last_ts") or 0.0,
           "model": main.get("model") or "", "turns": turns}

    # The in-flight turn counts too, without being folded into the cached state.
    # While it is open the clock runs against wall time, so the display ticks
    # between transcript writes (long thinking, streaming) instead of freezing.
    # IDLE_GRACE keeps an interrupted/crashed turn from counting forever.
    open_span = 0.0
    if turns["turn_start"]:
        now = time.time()
        if turns["turn_open"] and now - turns["turn_last"] <= IDLE_GRACE:
            open_span = max(0.0, now - turns["turn_start"])
        else:
            open_span = max(0.0, turns["turn_last"] - turns["turn_start"])
    acc["work_total"] += open_span
    if open_span > 0:
        acc["last_turn"] = open_span
    return acc


PEERS_CACHE = os.path.join(tempfile.gettempdir(), "clstatus-peers.json")
PEERS_TTL = 10        # secs the peer count is reused
PEERS_ACTIVE = 120    # a transcript written within this many secs is "active"


def count_peers(own_path):
    """Other Claude Code sessions on this machine writing a transcript in the
    last PEERS_ACTIVE secs (they share the 5h/weekly windows). Cached 10s."""
    now = time.time()
    try:
        with open(PEERS_CACHE, "r", encoding="utf-8") as f:
            c = json.load(f)
        if now - float(c.get("ts") or 0) < PEERS_TTL:
            return int(c.get("n") or 0)
    except (OSError, ValueError, TypeError):
        pass
    n = 0
    own = os.path.normcase(os.path.abspath(own_path or ""))
    root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    try:
        with os.scandir(root) as it:
            for d in it:
                if not d.is_dir():
                    continue
                try:
                    with os.scandir(d.path) as jt:
                        for e in jt:
                            if not e.name.endswith(".jsonl"):
                                continue
                            if os.path.normcase(os.path.abspath(e.path)) == own:
                                continue
                            try:
                                if now - e.stat().st_mtime <= PEERS_ACTIVE:
                                    n += 1
                            except OSError:
                                pass
                except OSError:
                    pass
    except OSError:
        pass
    try:
        tmp = f"{PEERS_CACHE}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"ts": now, "n": n}, f)
        os.replace(tmp, PEERS_CACHE)
    except OSError:
        pass
    return n


MIX_PALETTE = [CYAN, GREEN, MAGENTA, YELLOW, BLUE, WHITE]
MIX_DIM = ("other", "summary", "system")


def mix_line(attr, hog, avail, lw=METER_LW):
    """Stacked bar of what fills the context since the last compaction, with
    the top three categories and the single largest tool result."""
    total = sum(attr.values()) if attr else 0
    if total < 1000:
        return ""
    bw = max(6, min(20, avail - lw - 11))
    cats = sorted(attr.items(), key=lambda kv: -kv[1])
    colors, ci = {}, 0
    for cat, _ in cats:
        if cat in MIX_DIM:
            colors[cat] = DIM
        else:
            colors[cat] = MIX_PALETTE[ci % len(MIX_PALETTE)]
            ci += 1
    cells = [[cat, int(round(tok * bw / total))] for cat, tok in cats]
    cells[0][1] += bw - sum(c for _, c in cells)
    bar = "".join(f"{colors[cat]}{'█' * c}{RESET}" for cat, c in cells if c > 0)
    legend = " · ".join(f"{colors[cat]}{cat}{RESET} {tok * 100 // total}%"
                        for cat, tok in cats[:3] if tok * 100 // total >= 1)
    if hog:
        legend += f" {DIM}· hog {hog[0]} {humanize(hog[1])}{RESET}"
    row = f" {METER_LABEL}{I_DIA} {'mix':<{lw}}{RESET} {bar}  {legend}"
    return vtrunc(row, avail)


IDLE_GRACE = 300  # secs of transcript silence after which an open turn is dead

FABLE_TTL = 60                       # secs before the cached usage is refreshed
FABLE_CACHE = os.path.join(tempfile.gettempdir(), "clstatus-fable.json")
FABLE_LOCK = FABLE_CACHE[:-5] + ".lock"
LOCK_STALE = 30                      # a worker older than this is presumed dead
SAMPLE_KEEP = 6 * 3600               # burn-rate history retained in the cache


def _iso_epoch(s):
    if not s:
        return 0
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return 0


def _read_cache():
    try:
        with open(FABLE_CACHE, "r", encoding="utf-8") as cf:
            c = json.load(cf)
        return c if isinstance(c, dict) else None
    except (OSError, ValueError):
        return None


def load_usage():
    """Rate-limit windows from the cache written by `--refresh-usage`.

    Never touches the network: when the cache is older than FABLE_TTL a
    detached worker is spawned and the stale data is rendered meanwhile.
    Returns (data, samples). data = {"five_hour"|"seven_day"|"fable":
    {"pct", "resets_at"}} or None; samples = [[ts, p5, p7], ...].
    """
    c = _read_cache()
    if c is None or time.time() - float(c.get("ts") or 0) >= FABLE_TTL:
        spawn_refresh()
    if c is None:
        return None, []
    return c.get("data"), c.get("samples") or []


def spawn_refresh():
    """Start one detached refresh worker, unless one is already running."""
    try:
        try:
            fd = os.open(FABLE_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(FABLE_LOCK) < LOCK_STALE:
                    return  # live worker
            except OSError:
                return
            fd = os.open(FABLE_LOCK, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        with os.fdopen(fd, "w") as lf:
            lf.write(str(os.getpid()))
        kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL, "close_fds": True}
        if sys.platform == "win32":
            kw["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            kw["start_new_session"] = True
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--refresh-usage"], **kw)
    except Exception:
        try:
            os.remove(FABLE_LOCK)
        except OSError:
            pass


def refresh_usage():
    """Worker: fetch the claude.ai usage endpoint, update cache + samples.

    The endpoint carries float utilization; the statusline payload only ints.
    On failure nothing is written, so the render side keeps its stale data.
    """
    try:
        cred_path = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
        with open(cred_path, "r", encoding="utf-8") as f:
            tok = json.load(f)["claudeAiOauth"]["accessToken"]
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json",
                     "anthropic-beta": "oauth-2025-04-20",
                     "User-Agent": "claude-code-statusline"})
        with urllib.request.urlopen(req, timeout=8) as r:
            body = json.load(r)
        data = {}
        for key in ("five_hour", "seven_day"):
            w = body.get(key)
            if isinstance(w, dict) and w.get("utilization") is not None:
                data[key] = {"pct": float(w["utilization"]),
                             "resets_at": _iso_epoch(w.get("resets_at"))}
        for lim in body.get("limits") or []:
            name = (((lim.get("scope") or {}).get("model") or {}).get("display_name") or "")
            if lim.get("kind") == "weekly_scoped" and name.lower() == "fable":
                data["fable"] = {"pct": float(lim.get("percent") or 0),
                                 "resets_at": _iso_epoch(lim.get("resets_at"))}
                break

        now = time.time()
        old = _read_cache() or {}
        samples = [s for s in (old.get("samples") or [])
                   if isinstance(s, list) and len(s) == 3 and now - s[0] <= SAMPLE_KEEP]
        samples.append([now,
                        (data.get("five_hour") or {}).get("pct"),
                        (data.get("seven_day") or {}).get("pct")])
        tmp = FABLE_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as cf:
            json.dump({"ts": now, "data": data, "samples": samples}, cf)
        os.replace(tmp, FABLE_CACHE)
    finally:
        try:
            os.remove(FABLE_LOCK)
        except OSError:
            pass


def burn(samples, idx, pct, lookback, now=None, min_span=300):
    """%-per-hour slope of samples[*][idx] over the last `lookback` secs.

    Walks back from the newest sample while the series is non-decreasing
    (a drop means the window reset). Needs >= 2 samples spanning >= min_span.
    Returns rate (%/h) or None.
    """
    now = now or time.time()
    pts = []
    prev = pct
    for s in reversed(samples):
        try:
            ts, v = float(s[0]), s[idx]
        except (TypeError, IndexError, ValueError):
            continue
        if v is None:
            continue
        v = float(v)
        if ts < now - lookback or v > prev + 0.05:
            break
        pts.append((ts, v))
        prev = v
    if len(pts) < 2:
        return None
    (t_new, v_new), (t_old, v_old) = pts[0], pts[-1]
    span = t_new - t_old
    if span < min_span:
        return None
    return (v_new - v_old) / (span / 3600.0)


def burn_note(rate, pct, reset_epoch, per_day=False):
    """Colored ' · 2.1%/h' (+ ' · empty in 40m' when it beats the reset)."""
    if rate is None:
        return ""
    unit = "%/d" if per_day else "%/h"
    shown = rate * 24 if per_day else rate
    note = f"{DIM} · {shown:.1f}{unit}{RESET}"
    if rate > 0.01 and reset_epoch:
        left_h = (100.0 - pct) / rate
        reset_h = (reset_epoch - time.time()) / 3600.0
        if 0 < left_h < reset_h:
            note += f"{RED}{BOLD} · empty in {fmt_dur(left_h * 3600)}{RESET}"
    return note


def autocompact_threshold(size):
    """Tokens at which Claude Code (2.1.280) auto-compacts: min(80% of the
    window, window-13K), lowered by CLAUDE_AUTOCOMPACT_PCT_OVERRIDE if set.
    CLAUDE_CODE_AUTO_COMPACT_WINDOW caps the window the threshold is taken from."""
    if size <= 0:
        return 0
    try:
        cap = int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW") or 0)
    except ValueError:
        cap = 0
    win = min(size, cap) if cap > 0 else size
    thr = min(win - round(win * 0.2), win - 13000)
    try:
        pct = float(os.environ.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE") or 0)
    except ValueError:
        pct = 0
    if 0 < pct <= 100:
        thr = min(int(size * pct / 100), thr)
    return max(0, thr)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    seg = []  # line-1 items: {"text", "prio", "compact"?}; prio 0 never dropped

    def push(text, prio=1, compact=None):
        seg.append({"text": text, "prio": prio, "compact": compact})

    # ── Model ──────────────────────────────────────────────────────────────
    model = data.get("model", {})
    model_id = model.get("id", "")
    ctx = data.get("context_window", {})
    size = int(ctx.get("context_window_size") or 0)
    short, one_m, matched = model_label(model_id, model.get("display_name", ""), size)
    if model_id:
        text = f"{BOLD}{WHITE}{short}{RESET}"
        if one_m:
            text += f" {DIM}1M{RESET}"
        if not matched:
            text += f" {DIM}({model_id}){RESET}"
        push(text, prio=0, compact=f"{BOLD}{WHITE}{short}{RESET}")

    # Transcript-derived state is needed by the ctx row and line 2 alike.
    u = parse_usage(data.get("transcript_path", ""))
    T = (u or {}).get("turns") or {}
    now = time.time()

    # ── Effort / reasoning ────────────────────────────────────────────────
    effort = data.get("effort", {})
    effort_level = effort.get("level", "") if effort else ""
    thinking = data.get("thinking", {})
    thinking_on = thinking.get("enabled", False) if thinking else False

    effort_parts = []
    if effort_level:
        ec = EFFORT_COLOR.get(effort_level, YELLOW)
        effort_parts.append(f"{ec}{effort_level}{RESET}")
    if thinking_on:
        effort_parts.append(f"{MAGENTA}thinking{RESET}")
    if effort_parts:
        push("effort: " + "+".join(effort_parts), prio=4)

    # ── Vim mode ──────────────────────────────────────────────────────────
    vim = data.get("vim", {})
    if vim:
        vmode = vim.get("mode", "")
        if vmode:
            vc = VIM_COLOR.get(vmode, WHITE)
            push(f"{vc}VIM:{vmode}{RESET}", prio=2)

    # ── Agent name ────────────────────────────────────────────────────────
    agent = data.get("agent", {})
    if agent:
        aname = agent.get("name", "")
        if aname:
            push(f"{DIM}agent:{aname}{RESET}", prio=5)

    # ── PR badge ──────────────────────────────────────────────────────────
    pr = data.get("pr", {})
    if pr:
        pr_num = pr.get("number", "")
        pr_state = pr.get("review_state", "open")
        if pr_num:
            pr_c = GREEN if pr_state == "approved" else RED if pr_state == "changes_requested" else YELLOW
            push(f"{pr_c}PR#{pr_num} {pr_state}{RESET}", prio=3)

    # ── Context window ────────────────────────────────────────────────────
    pct = float(ctx.get("used_percentage") or 0)
    cu = ctx.get("current_usage") or {}
    used = 0
    if cu and size:
        used = sum(int(cu.get(k) or 0) for k in
                   ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        pct = used * 100.0 / size
    elif size:
        used = int(pct * size / 100)
    meters = []  # stacked rows: (label, pct, note[, mark[, pct_color]])

    ctx_note, ctx_mark, ctx_pc = "", None, None
    if size:
        ctx_note = f"{DIM}{humanize(used)}/{humanize(size)}{RESET}"
        thr = autocompact_threshold(size)
        if thr:
            ctx_mark = thr / size
            # same bands the binary uses: warn 20K under the threshold, then compact
            ctx_pc = (RED + BOLD if used >= thr else
                      YELLOW if used >= thr - 20000 else "")
            if used >= thr:
                ctx_note += f" {RED}{BOLD}compacting{RESET}"
            elif used >= thr - 20000:
                ctx_note += f" {YELLOW}{humanize(thr - used)} to compact{RESET}"
            else:
                # median context growth per user turn -> turns left before the tick
                hist = [h for h in (T.get("ctx_hist") or []) if h > 0]
                if len(hist) >= 2:
                    med = sorted(hist)[len(hist) // 2]
                    n_turns = (thr - used) / med
                    tc = YELLOW if n_turns <= 2 else DIM
                    ctx_note += f" {tc}≈{max(1, round(n_turns))} turns to compact{RESET}"
        if T.get("compactions"):
            ctx_note += f" {DIM}⟲{T['compactions']}{RESET}"

    # ── Rate limits ───────────────────────────────────────────────────────
    rl = data.get("rate_limits", {})
    rl5 = rl.get("five_hour", {}); rl7 = rl.get("seven_day", {})
    p5 = float(rl5.get("used_percentage", 0) or 0)
    p7 = float(rl7.get("used_percentage", 0) or 0)
    r5_epoch = rl5.get("resets_at", 0) or 0
    r7_epoch = rl7.get("resets_at", 0) or 0

    # endpoint has float utilization; payload only has ints. Prefer endpoint.
    # load_usage never blocks: it renders the cache and refreshes in a worker.
    api, samples = load_usage()
    api = api or {}
    if api.get("five_hour"):
        p5 = api["five_hour"]["pct"]; r5_epoch = api["five_hour"]["resets_at"] or r5_epoch
    if api.get("seven_day"):
        p7 = api["seven_day"]["pct"]; r7_epoch = api["seven_day"]["resets_at"] or r7_epoch

    def reset_note(txt):
        return f"{DIM}resets {txt}{RESET}" if txt else ""

    n5 = reset_note(fmt_reset_5h(r5_epoch)) + burn_note(
        burn(samples, 1, p5, 3600), p5, r5_epoch)
    n_peers = count_peers(data.get("transcript_path", ""))
    if n_peers:
        n5 += f"{DIM} · ◉ {n_peers + 1} sessions{RESET}"
    n7 = reset_note(fmt_reset_7d(r7_epoch)) + burn_note(
        burn(samples, 2, p7, SAMPLE_KEEP, min_span=3600), p7, r7_epoch, per_day=True)

    meters.append(("ctx", pct, ctx_note, ctx_mark, ctx_pc))
    meters.append(("5h", p5, n5))
    meters.append(("wk", p7, n7))

    fab = api.get("fable")
    pf = fab["pct"] if fab else 0
    if fab:
        meters.append(("fable", pf, reset_note(fmt_reset_7d(fab.get("resets_at", 0)))))

    if p5 >= 100 or p7 >= 100 or pf >= 100:
        push(f"{RED}{BOLD}{BLINK}RATE LIMITED{RESET}", prio=0)

    # ── Line 2: token throughput ───────────────────────────────────────────
    line2 = []  # same item shape; later/optional items get higher prio

    def push2(text, prio=1, compact=None):
        line2.append({"text": text, "prio": prio, "compact": compact})

    if u:
        # ── now-doing: open tool call / streaming / waiting on you ────────
        recent = bool(T.get("turn_last")) and now - T["turn_last"] <= IDLE_GRACE
        ot = T.get("open_tools") or {}
        if ot and recent:
            name, summ, ts0 = min(ot.values(), key=lambda v: v[2] or now)
            el = max(0.0, now - (ts0 or now))
            wc = YELLOW if el > 60 else CYAN
            more = f" +{len(ot) - 1}" if len(ot) > 1 else ""
            push2(f"{wc}⏳ {name}{more} {fmt_dur(el)}{RESET}"
                  + (f" {DIM}· {summ}{RESET}" if summ else ""), prio=1,
                  compact=f"{wc}⏳ {name} {fmt_dur(el)}{RESET}")
        elif T.get("turn_open") and recent:
            push2(f"{GREEN}▶ working {fmt_dur(now - T['turn_last'])}{RESET}", prio=1,
                  compact=f"{GREEN}▶{RESET}")
        elif T.get("turn_last"):
            push2(f"{DIM}⏸ your turn {fmt_dur(now - T['turn_last'])}{RESET}", prio=1,
                  compact=f"{DIM}⏸{RESET}")

        total_up = u["fresh"] + u["cache_read"]
        up = humanize(total_up)
        down = humanize(u["down"])
        push2(f"{CYAN}{BOLD}↑{RESET} {up} up  "
              f"{MAGENTA}{BOLD}↓{RESET} {down} down", prio=0,
              compact=f"{CYAN}{BOLD}↑{RESET}{up} {MAGENTA}{BOLD}↓{RESET}{down}")

        if total_up > 0:
            hit = u["cache_read"] * 100.0 / total_up
            hc = GREEN if hit >= 80 else YELLOW if hit >= 50 else DIM
            txt = f"{hc}cache {int(hit)}%{RESET}"
            ttl, lts = u.get("ttl") or 0, u.get("last_ts") or 0
            if ttl and lts:
                left = ttl - (now - lts)
                if left > 0:
                    wc = YELLOW if left < 300 else DIM
                    txt += f"{wc} · warm {fmt_dur(left)}{RESET}"
                else:
                    txt += f"{YELLOW} · cold, rewrites {humanize(u['last_up'])}{RESET}"
            push2(txt, prio=2, compact=f"{hc}cache {int(hit)}%{RESET}")

        if u["last_up"] or u["last_down"]:
            push2(f"{DIM}Δ ↑{humanize(u['last_up'])} "
                  f"↓{humanize(u['last_down'])}{RESET}", prio=3)

        aup = u.get("agent_fresh", 0) + u.get("agent_cache_read", 0)
        adn = u.get("agent_down", 0)
        if aup or adn:
            n = u.get("agent_n", 0)
            push2(f"{DIM}⚇ {n} agent{'s' if n != 1 else ''} "
                  f"↑{humanize(aup)} ↓{humanize(adn)}{RESET}", prio=3,
                  compact=f"{DIM}⚇{n} ↑{humanize(aup)}{RESET}")

        if u.get("work_total"):
            push2(f"{YELLOW}{BOLD}⏱{RESET} {fmt_dur(u['work_total'])} work",
                  prio=1,
                  compact=f"{YELLOW}{BOLD}⏱{RESET}{fmt_dur(u['work_total'])}")
        if u.get("last_turn"):
            push2(f"{DIM}turn {fmt_dur(u['last_turn'])}{RESET}", prio=3)

    # lines changed (only if the payload carries them)
    cost = data.get("cost", {}) or {}
    la = int(cost.get("total_lines_added", 0) or 0)
    lr = int(cost.get("total_lines_removed", 0) or 0)
    if la or lr:
        push2(f"{GREEN}+{la}{RESET} {RED}-{lr}{RESET}", prio=2)

    # ── tee usage to a snapshot read by projects/analysis/ui (main.js) ────
    try:
        snap = {
            "ts": time.time(),
            "model": model_id,
            "ctx_pct": pct,
            "five_hour": {"pct": p5, "resets_at": r5_epoch},
            "seven_day": {"pct": p7, "resets_at": r7_epoch},
            "cost_usd": cost.get("total_cost_usd"),
            "session": os.path.splitext(os.path.basename(data.get("transcript_path", "") or ""))[0],
        }
        snap_path = os.path.join(os.path.expanduser("~"), ".claude", "usage_snapshot.json")
        tmp = snap_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as sf:
            json.dump(snap, sf)
        os.replace(tmp, snap_path)
    except Exception:
        pass

    # ── Fit each line to the current terminal width ────────────────────────
    # Leading space + padding:1 (settings) + interface gutter ≈ 3 cols reserved.
    avail = max(24, term_cols() - 3)
    lines = [" " + fit_line(seg, avail, SEP)]
    lines += meter_lines(meters, avail)
    ml = mix_line(T.get("attr") or {}, T.get("hog"), avail)
    if ml:
        lines.insert(2, ml)  # right under the ctx row
    l2 = fit_line(line2, avail, SEP)
    if l2:
        lines.append(" " + l2)
    out = "\n".join(lines)
    sys.stdout.write(out + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        if "--refresh-usage" in sys.argv[1:]:
            refresh_usage()
        else:
            main()
    except Exception:
        pass
