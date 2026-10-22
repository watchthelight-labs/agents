<!-- <wtl> project: agents | file: docs/devices.md | author: watchthelight </wtl> -->
# Devices: phone, Windows, macOS

Three places I work from: my iPhone, and one laptop (a Lenovo Legion 5 15IAX10) that boots either Windows 11 or macOS 26.7.1 through OpenCore. They never run at the same time on the laptop, so most of the plumbing is about handing work from one OS to the other without losing anything.

## The channels

| From → to | Channel | What travels on it |
|---|---|---|
| any → any | **watchthelight memory** (MCP server) | Facts, decisions, open loops, handoff notes, credentials. Every Claude Code session on either OS loads it at start (four boot blocks); Claude web reads and writes the same notes |
| phone → laptop | **Claude web + a skill** | During a boot test the screen is the only output. I photograph it, the `legion-boot-screen` skill on claude.ai transcribes it word for word and saves a "Legion N-xx screen" note; `/legion-check` on the laptop picks it up |
| phone → laptop | **Tailscale** | SSH into the laptop from the phone (Windows or macOS side). Taildrop for files, only as a fallback because iPhone RAW photos are 70 MB |
| Windows ↔ macOS | **Git** | The project repo, pushed before every reboot. `docs/session-handoff.md` in it says what the last session did and what's next |
| Windows ↔ macOS | **USB stick** | The OPENCORE stick's `For Mac` folder for files that don't belong in git (screenshots, benchmarks) |
| Windows ↔ macOS | **this repo** | Skills and hooks: edit on one side, `collect.py` + push, `install.py --pull` on the other |
| GitHub → me | **Discord** | One org webhook posts every commit, issue and release in watchthelight-labs; two Actions add upstream news (see [upstream.md](upstream.md)) |
| laptop → phone | **ntfy** | The Stop hook pings my phone when a long turn finishes or Claude needs an answer |

## A typical reboot

1. **Before the reboot:** the Windows session writes a handoff note (memory + `session-handoff.md`) and pushes.
2. **On the Mac:** Claude Code boots, sees the handoff in the "threads" block, pulls, and carries on.
3. **If the boot fails:** before there's a desktop, the phone is the witness. A photo goes to Claude web, then into memory, then `/legion-check` reads it.
4. **Coming back to Windows:** the Mac session hands off the same way.

## Why memory instead of files

Notes in the memory server are searchable from every surface (Claude Code on both OSes, claude.ai on the phone, ChatGPT). They carry dates and a staleness flag, and they survive reinstalls. Files are for evidence and code, memory is for what we know.
