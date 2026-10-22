# Supersearch — Example Invocations

`/supersearch` is global. Invoke it from any project. It is always exhaustive — there are no quick/deep modes.

## Enter mode (no topic) — prints the welcome, then waits

```text
/supersearch
```

## Start exhaustive research immediately

```text
/supersearch whether React Server Components are production-ready in 2026

/supersearch best architecture for a local-first Electron + React + SQLite app

/supersearch Claude Code vs Codex CLI vs Cursor for autonomous software engineering workflows

/supersearch verify the claim that KVS Player V6 is commonly used for piracy or adult tube sites
```

## Mode commands (while Supersearch Mode is active)

```text
exit                          leave Supersearch Mode
cancel                        stop the running workflow, summarize what's done
help                          compact explanation of what the mode does
status                        current phase, agents returned, source/insight counts, what remains
refine: focus on self-hosting and ignore managed cloud options
sources: primary sources only — no vendor blogs
angle: evaluate everything from a security and supply-chain risk angle
```

## Typical flow

1. `/supersearch <topic>` → Phase 0 intent + Phase 1 plan (12–16 aspects) shown to you.
2. Workflow fans out: aspect agents → source audit → contradiction hunt → timeline → practitioner reality → devil's advocate → synthesis-prep → quality gate.
3. Quality gate verdict (PASS / WARN / FAIL) reported; one auto re-research pass on FAIL.
4. Final dossier written (and optionally saved as `supersearch-<slug>.md`).
5. Mode stays active — go deeper, change `angle:`/`sources:`, or `exit`.

## Notes

- Mid-research, drop a `refine:` / `sources:` / `angle:` line to steer without restarting from scratch.
- High-stakes topics (legal, medical, financial, security, safety) automatically raise source standards and flag uncertainty.
- A bare non-command message while in mode is treated as the research topic (or a follow-up if a dossier already exists).
