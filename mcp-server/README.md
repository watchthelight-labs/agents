<!-- <wtl> project: agents | file: mcp-server/README.md | author: watchthelight </wtl> -->
# watchthelight memory server

My long-term memory for AI agents, as one MCP server that every agent connects to: Claude Code on both of my operating systems, Claude on the web and phone, and ChatGPT. It holds four things:

- **Notes:** short, dated facts, decisions, gotchas, preferences and open loops. Agents write them as they work, without being asked (see [docs/memory.md](../docs/memory.md)). Every write is versioned and can be reverted.
- **Archive:** about 21,000 imported files (old chats, exports, docs) split into passages and searchable with SQLite FTS5. Agents cite the source and passage.
- **Vault:** credentials encrypted with AES-256-GCM. Agents see names only, and reading a value needs a stated reason that is logged.
- **Projects:** folders and git remotes mapped to a project, so a session started in a repo gets that project's notes at boot.

Python 3.11, the official `mcp` SDK over Streamable HTTP, SQLite. One small VPS runs it behind nginx. Nothing here phones home.

## How the pieces fit

```
Claude Code ──Bearer──┐
claude.ai ───OAuth────┼──► nginx (TLS) ──► memory-mcp serve  (127.0.0.1:8091) ──► /srv/memory-mcp/data
ChatGPT ─────OAuth────┘                     memory-mcp dash   (127.0.0.1:8092) ──┘  (notes, archive, vault,
browser ──Cloudflare Access──► nginx ──► dashboard SPA + /api                         oauth state)
inbox (scp) ──► memory-mcp-import.timer (every 2 min)       memory-mcp-backup.timer (daily)
```

- **Auth for Claude Code:** a static Bearer token (`MEMORY_TOKEN`).
- **Auth for claude.ai and ChatGPT:** OAuth through the SDK: dynamic client registration, PKCE, a consent page with CSRF protection, a scrypt-hashed owner password, rate-limited sign-in, one-hour access tokens, rotating 30-day refresh tokens. Notes marked private never reach OAuth clients.
- **Dashboard:** a React app plus a small JSON API, reachable only through Cloudflare Access. The API checks the Access JWT itself, and the Origin header on writes.
- **systemd hardening:** its own system user, `ProtectSystem=strict`, `ProtectHome`, `NoNewPrivileges`, a memory cap, and write access only to the data folder.

## Tools

`boot`, `search_memory`, `read_source`, `list_sources`, `read_note`, `list_notes`, `remember`, `verify_note`, `archive_note`, `restore_note`, `relabel_note`, `list_changes`, `revert_change`, `list_projects`, `set_project`, `delete_note`, `forget_source`, `memory_status`, `list_credentials`, `get_credential`, `put_credential`, `delete_credential`, `credential_audit`, plus a `boot_prompt` prompt and a plain `/boot` route the Claude Code hooks use.

The server's instructions tell every client to call `boot` first. On the next note it saves, a client gets back a receipt line ("saved: … · undo #812"), which it shows to the user.

## Setting it up

You need a Linux server with a public address (any small VPS), a domain, Python 3.11+, nginx and certbot. Node is only needed to build the dashboard.

1. **Pick your names.** This copy uses `mcp.example.org` for the server and `dash.example.org` for the dashboard. Search and replace them with yours across `ops/` and `src/` (`auth.py` has the issuer, `server.py` the allowed hosts and origins).
2. **Create the secrets.** These are local and never committed:
   ```sh
   pip install -e .                             # gives the memory-mcp command
   memory-mcp vault new-key                     # MEMORY_VAULT_KEY
   python -c "import secrets; print(secrets.token_urlsafe(48))"                       # MEMORY_TOKEN (Claude Code)
   python -c "from memory_mcp.auth import password_hash; print(password_hash('...'))" # MEMORY_PASSWORD_HASH
   ```
   Put them, with `MEMORY_USERNAME` and `MEMORY_DATA=/srv/memory-mcp/data`, in `memory-mcp.env`. For the dashboard add `memory-dash.env` with `CF_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `OWNER_EMAIL`, `DASH_SECRET` and `DASH_ORIGINS`.
3. **DNS.** Point both names at the server (`ops/create-dns.py` does it through Cloudflare's API).
4. **Build and ship.** `python ops/build.py` builds the dashboard and packs `app.tar.gz`. Copy it, the two env files and `ops/install.sh` to the server, then run `sudo bash install.sh`. It does all of this:
   - creates the `memory-mcp` system user and `/srv/memory-mcp/{app,data,inbox}`;
   - builds a venv from the hash-pinned `requirements.lock`;
   - installs the env files (never overwriting a live one, since it holds the vault key);
   - installs the systemd units and timers, and adds nginx vhosts for both names.

   `ops/enable-tls.sh` then gets the certificates.
5. **Lock down the dashboard.** Put it behind a Cloudflare Access application (`ops/cf-dash.py`) and use an Access origin certificate.
6. **Check it.** Run `ops/verify-remote.py` (health and tools), `ops/verify-oauth.py` (the whole OAuth flow) and `ops/verify-browser-login.py`.
7. **Connect clients.**
   - **Claude Code:** `claude mcp add --scope user --transport http watchthelight https://mcp.example.org/mcp --header "Authorization: Bearer <MEMORY_TOKEN>"`. `ops/configure-claude-code.py` does the same.
   - **claude.ai:** Settings → Connectors → Add custom connector, URL `https://mcp.example.org/mcp`, sign in once.
   - **ChatGPT:** the same URL as a custom connector.
8. **Feed it.** Drop `.md`, `.txt`, `.json`, `.jsonl` or `.csv` files in an inbox folder, and `ops/sync-inbox.py` uploads only new or changed ones over SSH. The import timer indexes them within two minutes. `ops/import-credentials.py` loads a credentials file into the vault.

Run the tests with `pip install -e ".[dev]" && pytest`. The fixtures in `tests/` use made-up secrets on purpose.

## What I'd tell someone copying this

- Make the agent save notes itself and show the receipt. Memory that depends on you remembering to save it stays empty.
- Keep notes small and dated, with a review date. Stale facts are worse than none, so the server flags them and agents check before acting.
- Never let a credential value enter a chat. The vault plus "names only unless there's a logged reason" works.
