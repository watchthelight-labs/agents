<!-- <wtl> project: agents | file: docs/usb.md | author: watchthelight </wtl> -->
# The two USB sticks

Both are SanDisk USB 3.2 sticks. One boots macOS, the other boots a tiny offline scanner. Agents may read and change the first one (always keeping a backup); the second one is touched only to collect reports.

## Stick 1: OPENCORE (28.7 GB)

| Partition | Size | What |
|---|---|---|
| `OPENCORE` (FAT32) | 8 GB | OpenCore (`EFI/`), the macOS Sequoia recovery (`com.apple.recovery.boot`), every OpenCore log (`opencore-*.txt`), config backups and a `For Mac` folder |
| two small partitions | 64 MB + 1 GB | left over from installer layouts |
| free | ~19 GB | |

**What it's for:**
- Boot medium, then fallback. It started as the only boot medium. Once the internal EFI partition took over, it became the known-good fallback: F12 -> USB brings back the last configuration that worked.
- Boot logs. OpenCore writes a log to the stick on every boot from it. `/legion-check` reads the newest one, redacts the machine's identity and files it as evidence (and in the public [research](https://github.com/watchthelight-labs/research) repo).
- Config backups. Before any change the agent copies `config.plist` to `config.N-xx.plist.bak` on the stick, so every attempt can be undone from the stick itself.
- Moving files. `For Mac` carries files between Windows and macOS that don't belong in git.
- Recovery. The Sequoia recovery is there for reinstalling or using Terminal when the internal install won't boot.

When Windows doesn't show the stick after a reboot, `pnputil /scan-devices` and `diskpart` -> `rescan` bring it back. Don't trust `Get-Volume` in an elevated shell for this.

## Stick 2: PROBE1401 (57 GB)

[NullMoth](https://nullmothsystems.com)'s **1401 Probe**: a small Linux system that boots, reads the hardware (CPU, board, firmware settings, GPUs and their firmware, Wi-Fi and Bluetooth chips, audio, USB, ACPI tables) and writes one report to the stick. It removes serials, UUIDs and MAC addresses from the report and never touches the internal drives (it locks them read-only first). It only works with Secure Boot off.

**What I added:**
- **`legion/xe-capture.sh`:** under real Linux drivers, records what the Intel iGPU looks like (registers, firmware, the driver's view). That's the reference the XeGfx port is checked against.
- **`support/`:** a reverse tunnel so an agent can reach the probe while it runs. Its keys stay on the stick and are not published anywhere.
- **`REPORTS/`:** one zip and one text summary per run, named after the machine.

To use it, boot it with F12 -> USB and let it scan (a minute or two); it powers off when done. Back in Windows, the agent reads `REPORTS/` and files what matters.
