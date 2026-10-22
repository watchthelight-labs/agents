<!-- <wtl> project: agents | file: docs/upstream.md | author: watchthelight </wtl> -->
# Keeping up with related projects

The projects ours build on, or that attack the same hardware, move fast. Three layers make sure none of it gets past me.

## 1. Discord feed, live

- **Org webhook:** every commit, issue, PR and release in watchthelight-labs posts to one Discord channel.
- **upstream-watch** (an Action in `watchthelight-labs/.github`, every 10 minutes): my pull requests to upstream projects, comments and reviews on them, merges, and mentions of me.
- **related-watch** (an Action in [research](https://github.com/watchthelight-labs/research), every 3 hours): new releases and commits in every project the scout follows, plus new comments from other people on our issues, especially ones with logs.

## 2. The scout, daily

The [`upstream-scout`](../claude/skills/upstream-scout/SKILL.md) skill is the deep version. It runs at 09:00 from a scheduled task (Windows Task Scheduler; launchd on macOS), at the end of every `/legion-check` (quick mode), and whenever I ask.

1. **Collect.** `scan.py` asks GitHub what changed since its cursor in about 60 related repos: commits (including feature branches), releases, merged PRs, issues that mention our hardware. It also searches GitHub for projects we don't know yet, and drops star lists and link dumps.
2. **Read.** Parallel readers go through the actual diffs and threads and answer the same questions for each one:
   - What changed?
   - Does it unblock or contradict something of ours?
   - Can we use it (licence)?
   - How sure are we?

   A web sweep covers the forums.
3. **Record.**
   - A write-up per project in the research repo, with a link for every claim.
   - A row in the project tracker's Research sheet.
   - A comment on any of our issues it bears on.
   - User logs from our issues go into the research repo, redacted.
4. **Credit.** Anything we learned from gets a line in that repo's credits section the same day, and claims it made false get corrected.

The first run found, among other things, that another project had the same Linux-driver-on-XNU architecture as ours drawing a full desktop on the GPU. It also found two of their bug fixes that apply to us directly.

## 3. Logs as research

Every log (ours from each boot attempt, and the ones users post) ends up in [watchthelight-labs/research](https://github.com/watchthelight-labs/research), sorted by person and machine. That repo's own redactor and privacy check run first.
