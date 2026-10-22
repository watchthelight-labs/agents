---
name: legion-boot-screen
description: Transcribe a Project Legion boot-screen photo (OpenCore / macOS verbose boot on Bash's Lenovo Legion 5) verbatim and save it to the watchthelight memory server so Claude Code can analyse it. Use whenever Bash uploads a photo of a boot screen, kernel panic, OpenCore picker or Hackintosh boot log, or says "legion screen", "boot photo", "save the screen".
---

# Legion boot screen -> watchthelight

Bash photographs the laptop screen during a native macOS boot attempt (Project Legion). Claude Code on the laptop reads the result from watchthelight. Your job is an exact transcription, not an analysis.

## Steps

1. **Attempt ID.** Use the ID Bash gives (N-xx). If none, call `search_memory` with query `Legion screen` (scope project:legion-hackintosh, newest first) and use the next number after the highest `Legion N-xx screen` note. Say which ID you picked.
2. **Transcribe every line of text in every photo, top to bottom, exactly as shown.** Keep hex values, GUIDs, paths, backslashes, brackets, `#[EB...]` codes, timestamps and punctuation exactly. Do not fix, translate, summarise or reorder. Where a character or word cannot be read with confidence, write `[unreadable]` (never guess hex digits). With several photos, label them Photo 1, Photo 2 in the order taken.
3. **Describe the screen state in one or two sentences:** frozen on a line, scrolling, rebooted, kernel panic, prohibited sign, black screen, Apple logo with progress bar, etc. Note what is last on screen.
4. **Time:** the time Bash gives, or the current time (America/New_York) and that it is the upload time, plus any timestamp visible on screen.
5. **Save** with the watchthelight `remember` tool:
   - title: `Legion N-xx screen` (exact format, the attempt ID)
   - type: `fact`, scope: `project:legion-hackintosh`, evidence_type: `self_report`
   - content: the transcription, then the screen state, then the time.
   - If `possible_duplicate` comes back for the same attempt (a second photo of the same boot), revise that note and append the new photo's lines instead of creating another note.
6. **Echo the receipt line** and tell Bash: "Saved as Legion N-xx screen. Tell Claude Code: check N-xx."

## Rules

- Exact text beats readability. One wrong hex digit can send the debugging the wrong way.
- Do not add diagnosis or advice to the note; Claude Code combines it with the OpenCore log from the USB stick.
- Never include serial numbers, MLB, ROM or UUID values if they appear on screen: replace them with `[identifier redacted]` (the project repo is public).
