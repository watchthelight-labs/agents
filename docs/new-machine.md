<!-- <wtl> project: agents | file: docs/new-machine.md | author: watchthelight </wtl> -->
# Setting up a new machine

Works the same on Windows and macOS. Needs Git, Python 3.9+, Node (for the caveman hooks) and Claude Code.

## 1. Install

```sh
git clone https://github.com/watchthelight-labs/agents ~/src/agents
python3 ~/src/agents/install/install.py --dry-run    # see what it will do
python3 ~/src/agents/install/install.py
```

What happens:
- skills go to `~/.claude/skills/`, hooks to `~/.claude/hooks/`, plus the statusline, `guardrails.json`, the theme and the commands;
- `settings.json` gets the hook wiring and the statusLine, with `python` on Windows and `python3` elsewhere. It's backed up first, and nothing else in it changes;
- any file that would be replaced with different content is kept as `<name>.bak`.

Run it again any time. With `--pull` it updates the repo first, and if nothing changed it does nothing.

## 2. The three secrets (by hand, never in this repo)

1. **Memory server token**: put the Bearer token in `~/.claude/state/wtl/token` (one line), and add the server to Claude Code:
   ```sh
   claude mcp add --scope user --transport http watchthelight https://mcp.example.org/mcp \
     --header "Authorization: Bearer $(cat ~/.claude/state/wtl/token)"
   ```
   Use your own server's address. Copy the token from a machine that already has it, or from your password manager. It never goes through chat or this repo.
2. **Notifications** (optional): `~/.claude/notify.json` with your ntfy topic URL. `python3 ~/.claude/hooks/notify.py --test` checks it.
3. **Codex / other agents**: their own auth files, if you use them.

## 3. Check

Start `claude` in any folder. You should see four "watchthelight boot" blocks at the top: profile, infra, project, threads. You should also see the caveman banner and the status line. `/cmdlog --summary` should answer, and so should `/quota`.

## Keeping both machines in step

- Change a skill or hook on one machine.
- On that machine, run `python install/collect.py` in this repo. It copies the published files back, sanitizes them and runs the scan. Then commit and push.
- On the other machine, run `python3 install/install.py --pull`.

On the Legion, Windows is where `collect.py` normally runs. The private replacement list it needs (`~/.config/agents/private.json`) is kept in the private project repo.
