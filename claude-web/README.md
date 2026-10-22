<!-- <wtl> project: agents | file: claude-web/README.md | author: watchthelight </wtl> -->
# Skills for claude.ai

These run in Claude on the web and on the phone, not in Claude Code. To install one: zip its folder (the zip must contain the folder with `SKILL.md` at its top), then upload it in claude.ai under Settings → Capabilities → Skills.

They expect the watchthelight memory server to be connected as a custom connector (see [mcp-server](../mcp-server)), because that's where they leave their results for Claude Code to pick up.

| Skill | What |
|---|---|
| [legion-boot-screen](skills/legion-boot-screen/SKILL.md) | From a photo of a boot screen (OpenCore picker, verbose boot, panic text), writes a word-for-word transcription and saves it as a "Legion N-xx screen" note. `/legion-check` in Claude Code reads it next. |
