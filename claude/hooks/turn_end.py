#!/usr/bin/env python3
"""Stop: turn receipt -> ~/.claude/ledger.jsonl (+ toast/ntfy when it was a long
turn or agents ran). Notification: 'Claude needs you' for input prompts.

Reuses the statusline sidecar: parse_usage() records the byte offset and
token totals at each user prompt, so the turn that just ended is
(now - t0). Agent files touched during the turn are summed by model.
"""

import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402
import notify as N  # noqa: E402

sl = H.sl


def agent_turn(agent_dir, since):
    """Tokens of every agent transcript written since `since`, by model."""
    by_model, n, descs = {}, 0, []
    try:
        names = os.listdir(agent_dir)
    except OSError:
        return by_model, n, descs
    for name in names:
        if not (name.startswith("agent-") and name.endswith(".jsonl")):
            continue
        p = os.path.join(agent_dir, name)
        try:
            if os.path.getmtime(p) < since - 5:
                continue
        except OSError:
            continue
        seen = {}
        for rec in H.iter_records(p):
            if rec.get("type") != "assistant":
                continue
            if sl._tstamp(rec.get("timestamp")) < since - 5:
                continue
            m = rec.get("message") or {}
            u = m.get("usage")
            if not u:
                continue
            v = [int(u.get(k, 0) or 0) for k in sl.USAGE_KEYS]
            mid = m.get("id") or rec.get("uuid")
            old = seen.get(mid)
            seen[mid] = ([max(a, b) for a, b in zip(old[0], v)] if old else v, m.get("model") or "?")
        if not seen:
            continue
        n += 1
        for v, model in seen.values():
            bm = by_model.setdefault(model, {"up": 0, "cache_read": 0, "down": 0})
            bm["up"] += v[0] + v[1]
            bm["cache_read"] += v[2]
            bm["down"] += v[3]
        meta = H.load_json(p[:-6] + ".meta.json", {})
        if meta.get("description"):
            descs.append(meta["description"])
    return by_model, n, descs


def turn_details(tp, offset):
    """From the turn's first record on: prompt snippet, files written, tool calls."""
    prompt, files, tools = "", [], 0
    for rec in H.iter_records(tp, offset):
        if rec.get("isSidechain"):
            continue
        m = rec.get("message") or {}
        if not prompt and H.is_real_prompt(rec):
            prompt = " ".join(H.prompt_text(m.get("content")).split())[:160]
        elif rec.get("type") == "assistant":
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tools += 1
                    i = b.get("input") or {}
                    if b.get("name") in H.FILE_TOOLS and isinstance(i, dict):
                        p = i.get("file_path") or i.get("notebook_path")
                        if p and p not in files:
                            files.append(p)
    return prompt, files, tools


def on_stop(d, cfg):
    if d.get("stop_hook_active"):
        return
    tp = d.get("transcript_path") or ""
    u = sl.parse_usage(tp)
    if not u:
        return
    T = u["turns"]
    t0 = float(T.get("turn_start") or 0)
    if not t0:
        return
    now = time.time()
    secs = max(0.0, now - t0)
    m_up = (u["fresh"] - u["agent_fresh"]) - int(T["t0_main"][0])
    m_cr = (u["cache_read"] - u["agent_cache_read"]) - int(T["t0_main"][1])
    m_dn = (u["down"] - u["agent_down"]) - int(T["t0_main"][2])
    sess = os.path.splitext(os.path.basename(tp))[0]
    by_model, a_n, descs = agent_turn(os.path.join(os.path.dirname(tp), sess, "subagents"), t0)
    a_up = sum(v["up"] + v["cache_read"] for v in by_model.values())
    a_dn = sum(v["down"] for v in by_model.values())
    prompt, files, tools = turn_details(tp, int(T.get("turn_offset") or 0))
    cwd = d.get("cwd") or ""
    model = u.get("model") or ""
    row = {"ts": now, "t0": t0, "secs": round(secs, 1), "sess": sess[:8], "cwd": cwd,
           "project": os.path.basename(cwd.rstrip("\\/")) or cwd, "model": model,
           "main": {"up": max(0, m_up), "cache_read": max(0, m_cr), "down": max(0, m_dn)},
           "agents": {"n": a_n, "up": a_up, "down": a_dn, "by_model": by_model, "jobs": descs[:12]},
           "files": len(files), "tools": tools, "prompt": prompt}
    H.append_jsonl(H.LEDGER, row)

    if secs >= float(cfg.get("min_turn_secs", 120)) or (a_n and cfg.get("always_if_agents", True)):
        short = sl.model_label(model)[0] if model else ""
        title = " · ".join(x for x in ("Claude done", short, sl.fmt_dur(secs)) if x)
        parts = [row["project"], f"↑{sl.humanize(m_up + m_cr + a_up)} ↓{sl.humanize(m_dn + a_dn)}"]
        if a_n:
            parts.append(f"{a_n} agent{'s' if a_n != 1 else ''}")
        if files:
            parts.append(f"{len(files)} file{'s' if len(files) != 1 else ''}")
        last = " ".join(str(d.get("last_assistant_message") or "").split())
        body = " · ".join(parts) + (f"\n{last[:140]}" if last else "")
        N.send(title, body, cfg)


def on_notification(d, cfg):
    nt = d.get("notification_type") or ""
    if nt not in (cfg.get("needs_input_types") or []):
        return
    if not H.cooldown_ok(f"notify-{nt}", float(cfg.get("needs_input_cooldown", 60))):
        return
    cwd = os.path.basename((d.get("cwd") or "").rstrip("\\/"))
    msg = " ".join(str(d.get("message") or d.get("title") or nt).split())
    N.send(f"Claude needs you · {cwd}" if cwd else "Claude needs you", msg[:200], cfg)


def main():
    d = H.read_input()
    cfg = N.config()
    ev = d.get("hook_event_name") or ""
    if ev == "Stop":
        on_stop(d, cfg)
    elif ev == "Notification":
        on_notification(d, cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
