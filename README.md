<!-- <wtl> project: agents | file: README.md | author: watchthelight </wtl> -->
# agents

How I work with AI agents, and everything that makes it work: the Claude Code skills and hooks I use every day, the memory server they all share, how my phone and both sides of my laptop stay in sync, the two USB sticks behind the Hackintosh work, how I keep up with related projects, and the two working methods (caveman and BMAD) that shape every session.

It's also the install source. A new machine (or a fresh macOS login) gets the whole setup with:

```sh
git clone https://github.com/watchthelight-labs/agents ~/src/agents
python3 ~/src/agents/install/install.py          # python on Windows
```

then the three secrets by hand ([docs/new-machine.md](docs/new-machine.md)). Or just tell Claude Code "set up from watchthelight-labs/agents".

## The setup at a glance

```
 iPhone ─── photos, Claude web ──► watchthelight memory ◄── every Claude Code session (boot hook)
   │                                  (mcp.example.org)          ▲                ▲
   └── SSH over Tailscale ──► Legion 5 15IAX10 ─────────────────┘                │
                                 ├─ Windows 11  ── Claude Code, hooks, skills ────┤
                                 └─ macOS 26.7.1 ─ Claude Code, same skills ──────┘
                                 USB 1: OPENCORE (boot fallback, logs, "For Mac")
                                 USB 2: PROBE1401 (offline hardware scanner)
 GitHub org ── org webhook + Actions ──► Discord channel (commits, releases, upstream news)
```

## What's here

| Path | What |
|---|---|
| [claude/skills/](claude/skills) | 17 Claude Code skills: boot-attempt analysis, upstream scouting, deep research, brainstorming, memory management, caveman, and more ([index](docs/skills.md)) |
| [claude/hooks/](claude/hooks) | The hooks behind every session: memory boot, guardrails, command audit log, per-turn ledger, compaction guard, quota advisory, notifications ([how they fit](docs/hooks.md)) |
| [claude/statusline/](claude/statusline) | The status line: model, context use, 5-hour and weekly quota with burn rate |
| [claude-web/skills/](claude-web/skills) | Skills uploaded to claude.ai (the boot-screen transcriber the phone uses) |
| [mcp-server/](mcp-server) | **watchthelight**, my memory MCP server: notes, a searchable archive, an encrypted credential vault, OAuth for claude.ai and ChatGPT, a dashboard. Full setup guide inside |
| [install/](install) | `install.py` puts it all in `~/.claude`; `collect.py` refreshes this repo from my machines (sanitized) |
| [docs/devices.md](docs/devices.md) | Phone, Windows and macOS: which channel carries what |
| [docs/usb.md](docs/usb.md) | The two USB sticks and the routines around them |
| [docs/upstream.md](docs/upstream.md) | How I find out what related projects did today |
| [docs/memory.md](docs/memory.md) | The memory protocol every agent follows |
| [docs/methods/caveman.md](docs/methods/caveman.md) | Caveman: terse replies by default, and when they switch off |
| [docs/methods/bmad.md](docs/methods/bmad.md) | BMAD: interrogate the idea before building, then build in gated phases |

## What isn't here

Secrets (tokens, keys, the vault, the server's private folder), my permission rules, personal project skills, skills built on code I can't share, and other people's skills I only use (those are linked in [THIRD-PARTY.md](THIRD-PARTY.md)). Everything published goes through `tools/scan.py` first, and CI runs it again on every push.

## Licence

ISC for my code ([LICENSE](LICENSE)). The caveman skills and hooks are vendored from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) under its Apache-2.0 / MIT terms ([licenses/](licenses)). The whatif skill bundles Paged.js (MIT) and the xkcd script font (CC BY-NC 3.0).
