#!/usr/bin/env python3
"""Where the quota went: report over ~/.claude/ledger.jsonl (one row per turn).

  quota.py [--window wk|5h|all|12h|3d] [--by project|model|hour|session|day]
           [--top 5] [--json]

Load = fresh input + 0.1 x cache reads + 5 x output (API price weights: a
better quota proxy than raw tokens). Share% divides each bucket's load by
(window load / window percent used), so it blends models and is approximate.
"""

import argparse, json, os, re, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

sl = H.sl
W_IN, W_CACHE, W_OUT = 1.0, 0.1, 5.0


def load_of(r):
    m, a = r.get("main") or {}, r.get("agents") or {}
    up = m.get("up", 0) + sum(v.get("up", 0) for v in (a.get("by_model") or {}).values())
    cr = m.get("cache_read", 0) + sum(v.get("cache_read", 0) for v in (a.get("by_model") or {}).values())
    dn = m.get("down", 0) + a.get("down", 0)
    return up * W_IN + cr * W_CACHE + dn * W_OUT, up, cr, dn


def window_start(name, cache):
    now = time.time()
    data = (cache or {}).get("data") or {}
    if name == "all":
        return 0, None
    if name == "wk":
        r = (data.get("seven_day") or {}).get("resets_at") or 0
        return (r - 7 * 86400) if r else now - 7 * 86400, (data.get("seven_day") or {}).get("pct")
    if name == "5h":
        r = (data.get("five_hour") or {}).get("resets_at") or 0
        return (r - 5 * 3600) if r else now - 5 * 3600, (data.get("five_hour") or {}).get("pct")
    m = re.fullmatch(r"(\d+)([hdw])", name)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return now - n * {"h": 3600, "d": 86400, "w": 604800}[u], None
    raise SystemExit(f"bad window: {name}")


def key_of(r, by):
    if by == "project":
        return r.get("project") or "?"
    if by == "session":
        return r.get("sess") or "?"
    if by == "hour":
        return datetime.fromtimestamp(float(r.get("t0") or r["ts"])).strftime("%H:00")
    if by == "day":
        return datetime.fromtimestamp(float(r.get("t0") or r["ts"])).strftime("%a %m-%d")
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", default="wk")
    ap.add_argument("--by", default="project", choices=["project", "model", "hour", "session", "day"])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cache = sl._read_cache()
    start, pct = window_start(a.window, cache)
    rows = [r for r in H.read_jsonl(H.LEDGER) if float(r.get("t0") or r.get("ts") or 0) >= start]
    if not rows:
        print(f"no ledger rows in window {a.window} ({H.LEDGER})")
        return

    agg = {}
    total_load = 0.0
    for r in rows:
        load, up, cr, dn = load_of(r)
        total_load += load
        if a.by == "model":
            m = r.get("main") or {}
            keys = {r.get("model") or "?": (m.get("up", 0) * W_IN + m.get("cache_read", 0) * W_CACHE + m.get("down", 0) * W_OUT,
                                             m.get("up", 0), m.get("cache_read", 0), m.get("down", 0))}
            for mdl, v in ((r.get("agents") or {}).get("by_model") or {}).items():
                l2 = v.get("up", 0) * W_IN + v.get("cache_read", 0) * W_CACHE + v.get("down", 0) * W_OUT
                k = f"{mdl} (agent)"
                o = keys.get(k, (0, 0, 0, 0))
                keys[k] = (o[0] + l2, o[1] + v.get("up", 0), o[2] + v.get("cache_read", 0), o[3] + v.get("down", 0))
        else:
            keys = {key_of(r, a.by): (load, up, cr, dn)}
        for k, (l, u_, c_, d_) in keys.items():
            g = agg.setdefault(k, {"turns": 0, "secs": 0.0, "load": 0.0, "up": 0, "cache_read": 0, "down": 0, "agents": 0})
            g["load"] += l; g["up"] += u_; g["cache_read"] += c_; g["down"] += d_
            if a.by != "model" or "(agent)" not in k:
                g["turns"] += 1; g["secs"] += float(r.get("secs") or 0)
                g["agents"] += int((r.get("agents") or {}).get("n") or 0)

    per_pct = (total_load / pct) if pct else None
    if a.json:
        print(json.dumps({"window": a.window, "start": start, "pct": pct, "load_per_pct": per_pct,
                          "by": a.by, "buckets": agg}, indent=1))
        return

    since = datetime.fromtimestamp(start).strftime("%a %m-%d %H:%M") if start else "ever"
    head = f"quota by {a.by} · window {a.window} since {since} · {len(rows)} turns · load {sl.humanize(int(total_load))}"
    if pct is not None:
        head += f" · window at {pct:.1f}%"
    print(head)
    print(f"{'bucket':<28} {'turns':>5} {'time':>7} {'fresh':>7} {'cached':>7} {'out':>6} {'agents':>6} {'load':>7} {'share':>6}")
    for k, g in sorted(agg.items(), key=lambda kv: -kv[1]["load"])[:40]:
        share = f"{g['load'] / per_pct:.1f}%" if per_pct else ""
        print(f"{str(k)[:28]:<28} {g['turns']:>5} {sl.fmt_dur(g['secs']):>7} {sl.humanize(g['up']):>7} "
              f"{sl.humanize(g['cache_read']):>7} {sl.humanize(g['down']):>6} {g['agents']:>6} {sl.humanize(int(g['load'])):>7} {share:>6}")
    if per_pct:
        print(f"share = load / ({sl.humanize(int(per_pct))} load per 1% of this window); blends models, treat as ±30%")
    if a.top:
        print(f"\ntop {a.top} turns by load")
        for r in sorted(rows, key=lambda r: -load_of(r)[0])[:a.top]:
            load, up, cr, dn = load_of(r)
            when = datetime.fromtimestamp(float(r.get("t0") or r["ts"])).strftime("%m-%d %H:%M")
            ag = (r.get("agents") or {}).get("n") or 0
            print(f"  {when}  {str(r.get('project') or '')[:18]:<18} {sl.fmt_dur(float(r.get('secs') or 0)):>7} "
                  f"load {sl.humanize(int(load)):>6}  ↑{sl.humanize(up + cr)} ↓{sl.humanize(dn)}"
                  + (f"  {ag} agents" if ag else "") + f"  {str(r.get('prompt') or '')[:60]}")


if __name__ == "__main__":
    main()
