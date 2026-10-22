---
name: memory-add
description: >
  Add something to the watchthelight MCP server (mcp.watchthelight.org): a note,
  a file or folder for the searchable archive, a single credential, or a whole
  credentials markdown/CSV file for the encrypted vault. Trigger: /memory-add
  <note|file|cred|creds-file> ... Use when Bash asks to remember, save, store,
  archive, or vault something in watchthelight.
user_invocable: true
arg_description: "note <text> | file <path> [--kind K] | cred <service> [fields…] | creds-file <path…> [--project P] [--tags a,b]"
---

Repo: `~\Projects\memory-mcp`. Run scripts with `uv run python` from there.
Tools are `mcp__watchthelight__*` (load via ToolSearch if deferred).

Pick the mode from `$ARGUMENTS`; if absent, infer from what Bash pasted.

## note
`remember(title, content, type, scope)`. type is `preference`, `fact`, `runbook`, `decision`, `gotcha`,
`open_loop` or `session_digest`; scope is `global` or `project:<key>` (pass `cwd` for a new project folder;
`list_projects` shows keys). Optional: `evidence_type` (`self_report` when it is Bash's own statement,
`assistant_summary` when you wrote it), `pinned` (leads every boot), `sensitivity: private` (kept out of boot and
away from claude.ai/ChatGPT), `source_date` only when Bash gave a date.
On `possible_duplicate`, revise the best candidate (`note_id` + `expected_version` from `read_note`) with merged content.
Echo the receipt line.

## file / folder → archive
1. Copy (never move) into `~\Documents\Memory-Inbox\<topic>\`. Allowed: .txt .md .json .jsonl .csv, UTF-8.
2. To set the kind, prepend front matter to the copy:
   ```
   ---
   kind: record            # curated|topic|session|record|reference|index|requests
   evidence_type: historical_mixed
   source_date: YYYY-MM-DD # only if known
   title: ...
   ---
   ```
3. `uv run python ops/sync-inbox.py`. The server indexes every 2 minutes and scrubs secret patterns plus exact vault values.
4. After ~2 minutes, confirm with `list_sources(source_prefix="inbox/")` or `search_memory`.

## cred → vault (single)
1. `list_credentials(query=<service>)` first. If it exists, replace with `put_credential(..., id, expected_version)`.
2. Otherwise `put_credential(service, fields={name: value}, label, project, tags)`. Fields named like
   password/key/token/secret/PIN are auto-marked secret. Pass `secret_fields` to override.
3. Confirm with `list_credentials`. Never echo the values back.

## creds-file → vault (bulk)
1. Dry run: `uv run python ops/import-credentials.py <paths> [--project P] [--tags a,b]`. This prints names and fields only.
   The parser handles `## Service` + `- **Label:** value`, `KEY=value`, 2-column tables, browser CSV
   (name,url,username,password,note), and `--raw` (whole file as one entry). It dedupes; later files win and older values are kept as `previous …`.
2. Show Bash the dry-run summary, then rerun with `--apply`. That runs over SSH into `memory-mcp vault import -`, upserting on (project, service, label).
3. Encrypted archives: extract into a fresh scratchpad folder, import, then delete the extracted copy.
4. Tag other people's credentials `third-party,do-not-use`.
5. Originals stay on disk unless Bash says otherwise.

Finish with one line: what was added and where (note id / inbox path / vault ids).
