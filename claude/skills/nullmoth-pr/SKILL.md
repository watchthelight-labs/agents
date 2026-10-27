---
name: nullmoth-pr
description: Prepare a pull request for nullmoth/nvidia-macos-driver from NvGfx fork commits, to upstream's own standards (one change per branch, their commit message form, no trace or diagnostic leftovers, comments that say why, compile check with their compiler line, the three template sections from tracker facts, prose lint). Leaves the "I wrote this myself" line for Bash. Trigger: /nullmoth-pr <fork commits or branch> [name], "prepare the PR for ...", "upstream this fix".
---

# NullMoth PR preparation

Upstream: github.com/nullmoth/nvidia-macos-driver, default branch `main`. Clean clone at `~/src/upstream-nmd` (partial
clone, `blob:none`: fetch fork commits with `git format-patch` + `git am -3`, a short SHA cannot be fetched). Fork commits
live in `~/src/NvGfx-2.4.3` (branch `nvgfx-2.4.3`, the fork on upstream v2.4.1; older lines in `~/src/NvGfx`). Drafts,
patches and the upstream-ready note go to `~/Hackintosh/evidence/native/<topic>/` (`UPSTREAM.md`, `PR-<branch>.md`,
`0001-<branch>.patch`) unless the request names another folder.

Read `~/src/upstream-nmd/CONTRIBUTING.md` and `.github/pull_request_template.md` first; they change.

## The rule that is not negotiable

The template ends with "I wrote this change and this description myself (not an AI tool), and I can explain every
line". That line stays unticked in anything this skill writes. Whether it becomes true is Bash's work (reading, rewriting,
testing until he can answer for every line) and ticking it is his act, done in his own file. The skill never rewrites code
or prose with the aim of hiding that an AI wrote it, and never adds text claiming human authorship. Quality edits are
fine; disguise is not.

## Steps

1. **Scope.** One change per branch. If the fork commits mix a fix with trace or diagnostic code, take only the fix.
   Branch name = the fix in two or three words (`fetch-off-zero-reads`, `a8-render-targets`).
2. **Branch.** `git -C ~/src/upstream-nmd fetch origin && git checkout -b <name> origin/main`; apply the fork commits
   with `git -C ~/src/NvGfx-2.4.3 format-patch -<n> <last-sha> --stdout | git am -3`; squash to one commit
   (`git reset --soft origin/main` then commit).
3. **Commit message.** `component: short summary` under 72 characters (`NVMTLDriver: ...`, `NVRMFB: ...`,
   `translator: ...`), then a plain paragraph: what was wrong, what the change does. Author `watchthelight
   <admin@watchthelight.org>`. No attribution trailers.
4. **Code audit (behaviour unchanged).** Remove `nvgfx_wstrace`, `nvlog` lines added only for the hunt, N-xx numbers,
   dates, "said once" counters that exist only for a capture, and comments that log when something was found. Keep
   comments that say why the code does what it does. Keep upstream's style (K&R-ish, one-line guards, their nvlog
   phrasing). Keep the `<wtl>` tags on Bash's hunks (his decision, 2026-10-19): `// <wtl>` ... `// </wtl>` stays in
   the PR branch. Strip tracker IDs (I-0xx, N-xxx) from comments. Diff the result against the fork commit to be sure no
   behaviour moved.
5. **Build.** Plugin: from `~/src/upstream-nmd/plugin`:
   `xcrun clang -arch x86_64 -mmacosx-version-min=15.0 -bundle -fobjc-arc -O1 -DNVMTL_RELEASE=1 -Wno-protocol
   -Wno-incomplete-implementation -Werror=unguarded-availability-new -I"$HOME/src/deps/Vulkan-Headers/include"
   -o <out>/NVMTLDriver NVMTLDevice.m -framework Foundation -framework Metal -framework IOSurface -framework IOKit
   -framework CoreFoundation` (upstream's line from `build/build_plugin_release.sh`; count ` error:` lines that start a
   diagnostic, not the ones quoting `(NSError **)err`; `vtool -show-build` must say minos 15.0).
   Translator: `cargo build --release --manifest-path translator/wrapper/Cargo.toml --target-dir <out>` with
   `~/.cargo/bin` on PATH. Kexts: say in the draft which boot ran them (upstream merges kext changes only after a boot
   on real hardware).
6. **Draft body.** The template's three headings, nothing else: What was wrong, What this changes, How I tested it (card,
   macOS version, what was run). Every test claim must point at a tracker row or an evidence folder (`scripts/tracker.py`,
   `evidence/native/N-xx/`). Card: RTX 5070 Laptop (GB206, 10DE:2D18), macOS 26.7.1 (25G241), Lenovo Legion 5 15IAX10.
   Short. No "Fixes #" unless an issue exists. The attestation line is not included; GitHub adds the template when the
   PR is opened on the web, and `nullpr` posts the file as given.
7. **Lint.** `python3 ~/.claude/skills/humanize/scripts/slop_lint.py <draft>` must report 0 hard; fix soft hits that
   read like a machine. No em dashes.
8. **Patch and record.** `git format-patch -1 HEAD --stdout > 0001-<name>.patch`; note branch, commit, files and build
   result in the handoff; `remember` the state under project:legion-hackintosh.
9. **Hand over.** Tell Bash the branch, the draft path and the `nullpr` line to run. Do not push, do not open the PR,
   do not create a fork (a new public repo needs his yes).

## Opening it

`nullpr <branch> "<title>" <body.md>` (in `~/.local/bin`) pushes the branch to `github.com/watchthelight/nvidia-macos-driver`
(creates the fork on first use, after asking) and opens a final PR against `nullmoth:main` with the body file as given.
`nullpr --edit <number> <body.md>` replaces an open PR's body.
