#!/usr/bin/env python3
"""Compaction survival kit.

PreCompact: save the facts a summary tends to drop (recent prompts verbatim,
standing constraints, files touched, background commands) to
~/.claude/compact-state/<session_id>.md.
SessionStart (source compact|resume): print that file so it re-enters context.
"""

import os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

STATE_DIR = os.path.join(H.CLAUDE_DIR, "compact-state")
CONSTRAINT_RE = re.compile(
    r"\b(never|don'?t|do not|always|only|must|no unasked|without asking|stop caveman|"
    r"keep .* (false|true|off|on))\b", re.I)
MAX_AGE = 48 * 3600


def collect(tp):
    prompts, files, seen, bg, constraints = [], [], set(), [], []
    compactions, cwd, branch = 0, "", ""
    for rec in H.iter_records(tp):
        if rec.get("isSidechain"):
            continue
        cwd = rec.get("cwd") or cwd
        branch = rec.get("gitBranch") or branch
        t = rec.get("type")
        m = rec.get("message") or {}
        if t == "system" and rec.get("subtype") == "compact_boundary":
            compactions += 1
        elif t == "user" and H.is_real_prompt(rec):
            txt = H.prompt_text(m.get("content")).strip()
            if re.fullmatch(r"/[\w-]+(\s+\S+){0,2}", txt):
                continue  # bare slash command (/compact, /exit ...), no task content
            prompts.append(txt)
            for s in re.split(r"(?<=[.!?\n])\s+", txt):
                s = s.strip()
                if 8 < len(s) <= 240 and CONSTRAINT_RE.search(s):
                    constraints.append(s)
        elif t == "assistant":
            for b in m.get("content") or []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                n, i = b.get("name"), b.get("input") or {}
                if not isinstance(i, dict):
                    continue
                if n in H.FILE_TOOLS:
                    p = i.get("file_path") or i.get("notebook_path")
                    if p and p not in seen:
                        seen.add(p)
                        files.append(p)
                elif n in H.SHELL_TOOLS and i.get("run_in_background"):
                    bg.append(" ".join(str(i.get("command") or "").split())[:160])
    return {"prompts": prompts[-6:], "constraints": list(dict.fromkeys(constraints))[-12:],
            "files": files[-40:], "bg": bg[-5:], "compactions": compactions,
            "cwd": cwd, "branch": branch}


def render(sess, info):
    out = [f"# compact-guard · session {sess[:8]} · saved {time.strftime('%Y-%m-%d %H:%M')} "
           f"· compaction #{info['compactions'] + 1}",
           f"cwd: {info['cwd']}" + (f"   branch: {info['branch']}" if info['branch'] else ""), ""]
    out.append("## Last user prompts, verbatim (oldest first)")
    for i, p in enumerate(info["prompts"], 1):
        p = p if len(p) <= 600 else p[:600] + " …"
        out.append(f"{i}. " + p.replace("\n", "\n   "))
    if info["constraints"]:
        out += ["", "## Standing constraints the user typed"]
        out += [f"- {c}" for c in info["constraints"]]
    if info["files"]:
        out += ["", "## Files written this session (Edit/Write), in order"]
        out += [f"- {f}" for f in info["files"]]
    if info["bg"]:
        out += ["", "## Background commands started"]
        out += [f"- {b}" for b in info["bg"]]
    return "\n".join(out) + "\n"


def main():
    d = H.read_input()
    ev = d.get("hook_event_name") or ""
    sess = d.get("session_id") or ""
    if not sess:
        return
    path = os.path.join(STATE_DIR, f"{sess}.md")
    if ev == "PreCompact":
        tp = d.get("transcript_path") or ""
        if not os.path.isfile(tp):
            return
        info = collect(tp)
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(render(sess, info))
        os.replace(tmp, path)
    elif ev == "SessionStart":
        if d.get("source") not in ("compact", "resume"):
            return
        try:
            if time.time() - os.path.getmtime(path) > MAX_AGE:
                return
            with open(path, "r", encoding="utf-8") as f:
                body = f.read()
        except OSError:
            return
        print("[compact-guard] Facts saved before the last compaction; they override "
              "anything the summary lost:\n\n" + body)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
