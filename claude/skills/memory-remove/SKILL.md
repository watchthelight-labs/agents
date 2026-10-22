---
name: memory-remove
description: >
  Remove something from the watchthelight MCP server: delete a note, forget an
  archive source (inbox or library file, with its revision history), or delete
  a vault credential. Always resolves and confirms the exact target first.
  Trigger: /memory-remove <note|source|cred> <query|id|uri>. Use when Bash asks
  to forget, delete, purge, or remove something from watchthelight.
user_invocable: true
arg_description: "note <id|query> | source <uri|query> [--keep-history] | cred <id|service> [--project P]"
---

Tools are `mcp__watchthelight__*` (load via ToolSearch if deferred).

For notes, prefer the soft path: `archive_note(note_id, reason)` retires it from boot and search but keeps it
restorable (`restore_note`, or `revert_change` on the archive's change id). Use it unless Bash says delete/erase/purge.
Hard deletion is permanent, and the server keeps no undo apart from the daily DB snapshot at `/srv/memory-mcp/data/backups/`.

## 1. Resolve and show the target. Never guess.
- **note**: a 32-hex id or the 8-hex prefix from boot/receipts is used directly. Otherwise `list_notes(title_contains=...)` or `search_memory(query, kind="note")`.
- **source**: an exact URI (`inbox/...`, `library/...`, `notes/...`) is used directly. Otherwise use `search_memory` / `list_sources`.
- **cred**: `list_credentials(query, project)`, then take `id` + `version`.

Show Bash a short table: URI or service, kind or project, title or fields, date. If more than one matches, ask which.
**Get an explicit yes for the specific items** before deleting, unless Bash already named the exact id or URI and said delete.

## 2. Delete
- note (soft, default): `archive_note(note_id, reason)`.
- note (hard): `delete_note(note_id, reason)` erases the note and all its revisions; the change log keeps a `delete` row.
- source: `forget_source(source, purge_history=true)`. `--keep-history` sets `purge_history=false`.
  A forgotten inbox file is not re-imported until its contents change.
- cred: `delete_credential(id, expected_version, reason)`. On a version conflict, re-list and retry.

## 3. Clean the local side for inbox sources (`inbox/<12-hex>/<relative path>`)
- Delete the matching local file under `~\Documents\Memory-Inbox\<relative path>`, if Bash wants that, and remove
  its key from `~\Projects\memory-mcp\private\inbox-sync.json`.
- Remove the server copy:
  `ssh -i ~/.ssh/memory-server.pem my-server "rm -- '/srv/memory-mcp/inbox/<12-hex>/<relative path>'"`

## 4. Verify
Re-run the resolving search or list. It should come back empty. Report what was removed in one line.
