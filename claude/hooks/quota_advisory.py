#!/usr/bin/env python3
"""UserPromptSubmit: one advisory line when the rate-limit window is about to
run dry, so Claude itself throttles agent fan-out. Reads the statusline's
usage cache (5h/7d percent + burn samples). At most once per 10 minutes.
"""

import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

sl = H.sl
COOLDOWN = 600
FIVE_H_WARN = 85.0
WEEK_WARN = 90.0


def main():
    d = H.read_input()
    if d.get("source") not in (None, "", "user"):
        return
    c = sl._read_cache() or {}
    data, samples = c.get("data") or {}, c.get("samples") or []
    now = time.time()
    lines = []

    fh = data.get("five_hour") or {}
    p5, r5 = float(fh.get("pct") or 0), float(fh.get("resets_at") or 0)
    rate = sl.burn(samples, 1, p5, 3600, now)
    reset_h = (r5 - now) / 3600 if r5 else 0
    empty_h = (100 - p5) / rate if rate and rate > 0.01 else None
    if p5 >= FIVE_H_WARN or (empty_h is not None and reset_h and empty_h < reset_h):
        msg = f"[quota] 5h window at {p5:.0f}%"
        if rate:
            msg += f", burning {rate:.1f}%/h"
        if empty_h is not None and reset_h and empty_h < reset_h:
            msg += f", empties in ~{sl.fmt_dur(empty_h * 3600)} (resets in {sl.fmt_dur(reset_h * 3600)})"
        elif reset_h:
            msg += f" (resets in {sl.fmt_dur(reset_h * 3600)})"
        msg += ". Prefer Sonnet/Haiku for agents, avoid fan-out, batch tool calls until the reset."
        lines.append(msg)

    sd = data.get("seven_day") or {}
    p7, r7 = float(sd.get("pct") or 0), float(sd.get("resets_at") or 0)
    if p7 >= WEEK_WARN:
        left = sl.fmt_dur(max(0, r7 - now)) if r7 else "?"
        lines.append(f"[quota] weekly window at {p7:.0f}%, resets in {left}. Keep work essential.")

    if lines and H.cooldown_ok("quota-advisory", COOLDOWN):
        print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
