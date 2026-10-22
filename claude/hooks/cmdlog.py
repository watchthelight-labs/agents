#!/usr/bin/env python3
"""Query the command audit log written by audit.py / guardrails.py.

  cmdlog.py [--since 2h|3d|YYYY-MM-DD] [--grep RE] [--tool Bash] [--session PFX]
            [--failed] [--files] [--guardrails] [--bg] [-n 40] [--summary] [--json]
"""

import argparse, json, os, re, shutil, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402


def parse_since(s):
    if not s:
        return 0
    m = re.fullmatch(r"(\d+)([smhdw])", s.strip())
    if m:
        n, u = int(m.group(1)), m.group(2)
        return time.time() - n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[u]
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return 0


def fmt_when(ts):
    t = datetime.fromtimestamp(ts)
    today = datetime.now().date()
    return t.strftime("%H:%M:%S") if t.date() == today else t.strftime("%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="1d")
    ap.add_argument("--grep")
    ap.add_argument("--tool")
    ap.add_argument("--session")
    ap.add_argument("--failed", action="store_true")
    ap.add_argument("--files", action="store_true", help="only file writes")
    ap.add_argument("--guardrails", action="store_true", help="only guardrail decisions")
    ap.add_argument("--bg", action="store_true", help="only background commands")
    ap.add_argument("-n", type=int, default=40)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = H.read_jsonl(H.CMDLOG)
    t0 = parse_since(a.since)
    rx = re.compile(a.grep, re.I) if a.grep else None
    sel = []
    for r in rows:
        if float(r.get("ts") or 0) < t0:
            continue
        if a.tool and (r.get("tool") or "").lower() != a.tool.lower():
            continue
        if a.session and not (r.get("sess") or "").startswith(a.session):
            continue
        if a.failed and r.get("ok", True):
            continue
        if a.files and r.get("tool") not in H.FILE_TOOLS:
            continue
        if a.guardrails and r.get("event") != "guardrail":
            continue
        if a.bg and not r.get("bg"):
            continue
        if rx and not (rx.search(r.get("cmd") or "") or rx.search(r.get("err") or "")
                       or rx.search(r.get("cwd") or "")):
            continue
        sel.append(r)

    if a.json:
        for r in sel[-a.n:]:
            print(json.dumps(r, ensure_ascii=False))
        return
    if not sel:
        print(f"no rows since {a.since} in {H.CMDLOG}")
        return
    if a.summary:
        by_tool, by_sess, fails = {}, {}, 0
        for r in sel:
            by_tool[r.get("tool")] = by_tool.get(r.get("tool"), 0) + 1
            by_sess[r.get("sess")] = by_sess.get(r.get("sess"), 0) + 1
            fails += 0 if r.get("ok", True) else 1
        print(f"{len(sel)} rows since {a.since}, {fails} failed, {len(by_sess)} sessions")
        print("by tool:   " + ", ".join(f"{k} {v}" for k, v in sorted(by_tool.items(), key=lambda kv: -kv[1])))
        print("by sess:   " + ", ".join(f"{k} {v}" for k, v in sorted(by_sess.items(), key=lambda kv: -kv[1])[:12]))
        return

    width = shutil.get_terminal_size((120, 20)).columns
    print(f"{'when':<11} {'sess':<8} {'tool':<10} {'dur':>6} ok  cmd")
    for r in sel[-a.n:]:
        dur = r.get("dur_ms")
        dur_s = f"{dur/1000:.1f}s" if isinstance(dur, (int, float)) else ""
        ok = "✓" if r.get("ok", True) else "✗"
        if r.get("event") == "guardrail":
            ok = "⛔"
        cmd = " ".join(str(r.get("cmd") or "").split())
        if r.get("event") == "guardrail":
            cmd = f"[{r.get('rule')}:{r.get('decision')}] {cmd}"
        if r.get("err") and not r.get("ok", True):
            cmd += f"  ← {' '.join(str(r['err']).split())[:80]}"
        line = f"{fmt_when(float(r.get('ts') or 0)):<11} {str(r.get('sess') or ''):<8} {str(r.get('tool') or ''):<10} {dur_s:>6} {ok}   {cmd}"
        print(line[:max(40, width - 1)])


if __name__ == "__main__":
    main()
