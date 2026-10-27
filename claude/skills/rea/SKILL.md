---
name: rea
description: Project Legion reverse engineering with a pinned, audited REA (morluto/rea) CLI plus the native macOS tools. Use for Mach-O and dyld shared cache frameworks (QuartzCore and friends), Apple GPU bundles and kexts, IOKit user-client selector mapping, NVIDIA and Intel Windows driver files (.sys, .dll, .inf), and OpenCore binaries. Trigger: /rea, "reverse this driver", "what does this kext export", "map the IOKit selectors", "inspect this PE". Read-only on system binaries.
---

# REA for Project Legion

Adapted from the `reverse-engineer-anything` skill of [morluto/rea](https://github.com/morluto/rea) (MIT, Copyright (c) 2026 morluto; notice in `licenses/rea-MIT.txt` of the agents repo). Checked 2026-10-24 against rea-agents 6.7.0. The upstream text moves daily; re-run the audit before changing the pin.

## What REA is here, and what it is not

REA is a Node CLI (`rea <command>`) with an MCP server around it. We use the CLI only, pinned to **rea-agents 6.7.0** (tarball sha256 `20958a66dba1a011e50a486beb9463a343128ed368c984f94065362c13f51f90`, npm sha512 `yhIx2ioJYYT1C/tONfYeitC6LhnKmCh+ZwRUOgYuhSc733lGhkkt73zhug9WmLgxoMdKuqIYGCoBfD4fXkOhFw==`), installed with `--ignore-scripts --omit=optional` into a private prefix. The audit is `research/repository-audits/rea.md` in the project repo.

REA has **no support** for the dyld shared cache, kexts (`MH_KEXT_BUNDLE`), kernelcaches or `MH_FILESET`, or IOKit analysis. It does not resolve `/System` libraries (they live in the cache). Its native decompilation drives Ghidra, Hopper or IDA; Ghidra 12.1.4 is installed on the Mac (2026-10-24), Hopper and IDA are not. Ghidra takes thin Mach-O slices only (`lipo -thin x86_64`). The macOS tools cover what REA cannot.

| Target | Use | Note |
|---|---|---|
| Mach-O file on disk (kext binary, GPU bundle dylib) | `rea inspect-macho <copy>`, `rea inspect-binary-layout`, `rea inspect-plist` | load commands, slices, UUID, dylib resolution, entrypoints |
| Framework in the dyld shared cache (QuartzCore, Metal, IOKit) | `dyld_info` and `lldb` (below), not REA | the on-disk path is a stub; REA cannot see the cache |
| PE driver or DLL (nvlddmkm.sys, igdkmdn64.sys, UMD dlls) | `rea inspect-pe-resources <copy>`, `rea inspect-artifact <copy>`; imports and exports with `llvm-objdump-mp-20 -p <copy>` | 6.7.0 has no PE imports, certificates or exports command (they exist only on the unreleased `main`, checked 2026-10-24); the Authenticode blob is not parsed |
| Apple crash logs (.ips) | read the JSON by hand (`python3 -m json.tool`) or `rea inspect-recorded-crash` for registers | no .ips command in 6.7.0 |
| Kext, IOKit selectors | `kmutil`, `ioreg`, `otool`, `llvm-objdump-mp-20`, `nm` | see the IOKit section |
| OpenCore | `ocvalidate`, `scripts/diag/redact-oclog.py` in the project; REA only for the `.efi` PE files | OC logs are never fed to REA unredacted |

Check `rea --help` for the exact command names of this version before relying on a name; docs on the REA `main` branch describe commands that 6.7.0 does not have. Verified working here on 2026-10-24: `rea --version`, `rea inspect-macho` on a copy of `/bin/ls`, and `rea inspect-pe-resources` and `rea inspect-artifact` on a copy of a Windows driver (`beep.sys`).

## Hard rules (project)

- **Copies only.** Copy the file into a scratch folder (`cp -p`), hash it, and point REA at the copy. Never at a live path under `/System`, `/Library/Extensions`, `/Volumes/OCEFI` or the Windows ESP.
- **Never run `trace_native_values`, `capture_*` or any command that launches a target** on a system binary, driver or anything not built by us. They launch the target under LLDB or Frida.
- **Never attach a debugger to WindowServer**, or to anything that owns the display, Metal or a GPU client. lldb is for a harmless throwaway process (`sleep 600`, a tiny test binary) that you started yourself.
- **Read-only on the system.** No SIP, AMFI, NVRAM, kext or boot-config change comes out of an RE session. Findings go in the repo as evidence.
- **Audit before third-party code.** No new tool, mirror or release runs before `research/repository-audits/<name>.md` exists. Never use `install.sh`, `npx`, `rea setup`, `rea update`, `@latest`, Hopper, or any REA look-alike repo (the audit has the list; `ReverseEngineer-Anything/REA-Github` ships malware).
- **Evidence in the repo.** Save raw outputs under `evidence/native/<N-xx or topic>/` (redacted: no serials, MACs, keys), and link them from the tracker row and the handoff.
- Public text passes `slop_lint.py` and has no em dashes. No private paths, serials or SMBIOS data in anything exported.

## Evidence discipline (from REA)

Label every claim in a write-up with one of: **observation** (a tool printed it, cite command and file hash), **derivation** (computed from observations, show the step), **inference** (a reading of the above, say what would disprove it), **unknown** (not yet checked). Keep summaries first: ask for a summary or a filtered view (`--filter-output`, `--token-limit` on text output only), page into detail only for the part you need, and never dump a whole disassembly into the context. Write big dumps to a file and grep them. Record the file's SHA-256 and the tool version with each result.

## macOS (this machine: Intel x86_64, Tahoe 26.7.1)

Installed (user-local, no sudo):

- `~/src/rea`: read-only shallow clone of morluto/rea at `cd1878f3fe934be403edff40e65ea20cb38ffe43` (no submodules; run nothing in it).
- `~/.local/opt/rea-agents-6.7.0`: the pinned package. `~/.local/bin/rea` is a wrapper that blocks `setup`, `update` and `uninstall`. `rea --version` prints `6.7.0`.
- Node 24.22.1 at `~/.local/opt/node`. System tools: `dyld_info`, `otool`, `nm`, `lldb`, `codesign`, `kmutil`, `ioreg`; MacPorts `llvm-objdump-mp-20`, `llvm-nm-mp-20`, `llvm-otool-mp-20`, `llvm-dwarfdump-mp-20` in `/opt/local/bin`.
- Ghidra 12.1.4 at `~/.local/opt/ghidra_12.1.4_PUBLIC` and Temurin JDK 21.0.13+9 at `~/.local/opt/jdk-21.0.13+9` (both sha256 matched the pins). The zip has no macOS decompiler, so it was built from `Ghidra/Features/Decompiler/src/decompile/cpp` with `make ghidra_opt sleigh_opt` (first `mkdir com_opt com_dbg ghi_opt sla_opt ghi_dbg sla_dbg && touch */depend`, otherwise the depend step wants `bfd.h` and the link fails on missing object dirs) and copied to `Ghidra/Features/Decompiler/os/mac_x86_64/{decompile,sleigh}`. The `rea` wrapper sets `GHIDRA_INSTALL_DIR` and `JAVA_HOME`; `rea doctor` shows ghidra, the native decompiler and Java healthy. Ghidra in 6.7.0 refuses universal Mach-O files: `lipo -thin x86_64 <copy> -output <copy>.x86` first. Checked with `rea analyze <thin copy of /usr/bin/true> --provider ghidra --json`.

### Frameworks in the dyld shared cache (QuartzCore, Metal, IOKit)

The cache sits in `/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/` (`dyld_shared_cache_x86_64h*`). `dyld_info` reads cache images by their normal path, read-only, and works (checked 2026-10-24 on QuartzCore):

```sh
dyld_info -arch x86_64 -linked_dylibs /System/Library/Frameworks/QuartzCore.framework/QuartzCore
dyld_info -arch x86_64 -exports  ... > $SCRATCH/qc-exports.txt     # then grep, never print all
dyld_info -arch x86_64 -objc     ...  ;  -imports ... ; -function_starts ... ; -disassemble ... > file
```

For code, load a harmless process of your own into lldb and read the image from memory: start `sleep 600 &`, then `lldb -p <pid>` (only a process you started), `image list QuartzCore`, `image dump symtab QuartzCore`, `disassemble -n <symbol>`, `memory read`. Detach with `detach`, kill the sleep. Never lldb a process that owns the display. Do not extract the whole cache or write into `/System`.

### Apple GPU bundles and kexts

`/System/Library/Extensions/AppleIntelICLGraphicsMTLDriver.bundle/Contents/MacOS/libigdmd.dylib` is a normal on-disk Mach-O. Copy it, then:

```sh
cp -p <bundle>/Contents/MacOS/libigdmd.dylib $SCRATCH/ && shasum -a 256 $SCRATCH/libigdmd.dylib
rea inspect-macho $SCRATCH/libigdmd.dylib          # slices, UUID, entrypoints
dyld_info -exports -imports -linked_dylibs $SCRATCH/libigdmd.dylib > $SCRATCH/libigdmd.info
llvm-objdump-mp-20 -d --no-show-raw-insn $SCRATCH/libigdmd.dylib > $SCRATCH/libigdmd.dis   # once, then grep
nm -u / otool -L / codesign -d --entitlements - as needed
```

Kext binaries: `kmutil showloaded --no-kernel` and `kmutil inspect -b <bundle id>` for what is loaded and which collection it came from; `kextfind`-style reading of `Info.plist` with `rea inspect-plist`; the binary with `otool -l`, `nm`, `llvm-objdump-mp-20`. Kernel and system kexts live inside the boot kernel collection on Tahoe, so many are not separate files; do not try to unpack the collection into `/System`.

### IOKit user-client selector mapping

REA has nothing for this; do it by reading:

1. In the kext copy, find the user-client class (`nm | grep -i UserClient`, `strings`), and its `externalMethod` / `getTargetAndMethodForIndex` / `IOExternalMethodDispatch` tables (`llvm-objdump-mp-20 -s -j __DATA_CONST --section=__const` or the disassembly of `externalMethod`). The dispatch table gives selector index, struct and scalar input and output counts.
2. In the user-space client (UMD dylib or framework), find the `IOConnectCallMethod`, `IOConnectCallStructMethod` and `IOConnectCallScalarMethod` call sites and the constant loaded into the selector argument.
3. Live view without touching a client: `ioreg -l -w0 -c <class>` for the registry entry, read-only.
4. Write the table as selector, name, input shape, output shape, source (function and address), and label each row observation or inference.

### Windows drivers copied to this Mac

Windows C: is mounted read-only at `/Volumes/Untitled`. Copy the file out first, then `rea inspect-pe-resources`, `rea inspect-artifact`, `llvm-objdump-mp-20 -p` (PE headers, import and export tables), `strings`. Decompile a `.sys` copy with `rea analyze <copy> --provider ghidra`.

## Windows session (installed 2026-10-24)

**Moved 2026-10-24:** the Windows toolkit now lives in its own workspace, `C:\Users\REA`. It is not Legion: it has its own `CLAUDE.md` and watchthelight project `rea`, and each target gets a folder made with `_toolkit\bin\new-target.ps1`. Tools are in `C:\Users\REA\_toolkit\opt`, wrappers in `_toolkit\bin`, audit copies in `_toolkit\audits`, the inventory in `_toolkit\README.md`. `~/.local/bin/rea(.cmd)` only forward there. Where this section says `~/.local/opt`, read `C:\Users\REA\_toolkit\opt`. For Legion work on Windows, copy the target into the REA workspace (or a Legion evidence folder) first.

Installed on the Legion's Windows side (Bash approved the full install, addon included, on 2026-10-24). Take REA only from `npm rea-agents`, `morluto/rea` or rea.tools: Windows is where the fake REA zips turn up.

- Node 24.22.1 portable at `~/.local/opt/node-v24.22.1-win-x64` (zip sha256 `d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5`, matched nodejs.org `SHASUMS256.txt`). The system Node (25.x) is outside REA's engines range, so the wrapper never uses it.
- rea-agents 6.7.0 in `~/.local/opt/rea-agents-6.7.0` (tarball sha256 as pinned above; `npm install --ignore-scripts --omit=optional --no-audit --no-fund <tgz>`). The addon `native/windows/build/rea-windows-x64.node` matched the audit (881,284 bytes, sha256 `28e0a01f74b30232db559bf98f574be82e5c71ad36a86e4c38fe7fb448029856`).
- Ghidra 12.1.4 at `~/.local/opt/ghidra_12.1.4_PUBLIC` (zip sha256 as pinned below). The Windows zip ships `decompile.exe`, so nothing is built. JDK: the installed Zulu 21 (`C:\Program Files\Zulu\zulu-21`). Ghidra 11.3.1 in `C:\tools` stays for the `decompile` skill.
- Wrappers: `~/.local/bin/rea.cmd` (PowerShell, cmd, the MCP) and `~/.local/bin/rea` (Git Bash). Both set `GHIDRA_INSTALL_DIR`, `JAVA_HOME` and `REA_ANALYSIS_PROVIDER=ghidra`, and refuse `setup`, `update` and `uninstall`.
- MCP: `claude mcp add --scope user rea -e REA_MCP_INPUT_SCHEMA_PROFILE=compact -- 'C:\Users\REA\_toolkit\bin\rea.cmd' mcp`.
- Checked: `rea doctor --json` reports node, ghidra, the native decompiler, Java and Windows native authority healthy. Hopper, Kuna and the `rea setup` registrations show as missing, which is expected (IDA, JADX and ILSpy were added later the same day, see below). `rea analyze <copy of beep.sys> --provider ghidra --json` returned 46 procedures in about 40 s cold.

Work on copies of `.sys`/`.dll` files outside `C:\Windows`; driver-store files are signed and in use, so copy, never edit. PowerShell is already Administrator here; add no elevation steps.

### Full toolkit on Windows (added 2026-10-24)

Bash asked for every engine REA can drive. Each has an audit in `research/repository-audits/` and lives under `~/.local/opt`; both wrappers set the env vars, so `rea` and the MCP find them with no flags.

| Lane | Tool | Env var in the wrapper | How to use |
|---|---|---|---|
| IDA | IDA Free 9.4 (`~/.local/opt/ida-free-9.4`, license next to `ida.exe`) + ida-free-mcp 1.1.3 (loopback patch, built on SDK 9.4.0) in `%APPDATA%\Hex-Rays\IDA Pro\plugins` | `REA_IDA_MCP_CONFIG` (`~/.local/opt/rea-ida/ida-mcp.json`, native, 127.0.0.1:13337) | Open IDA on a copy, press Ctrl-Alt-M, then `--provider ida` or `provider_id: "ida"`. Ctrl-Alt-M again to stop. IDA Free has no batch mode: `-A` and `-S` make it quit, so it can't be scripted. Its F5 is the cloud decompiler: each function goes to Hex-Rays, so nothing private or under NDA; use Ghidra for those. |
| Rizin | Rizin 0.9.1 | `REA_RIZIN_COMMAND` | `rea execute-rizin-command <copy> iIj`. Use the `j` forms (`iIj`, `aflj`, `iij`): plain output comes back with ANSI colors. Debug sessions are Linux only. |
| Cutter | Cutter 2.4.1 (2.5.0 can't load Python plugins on Windows, cutter#3659); REA bridge in `%APPDATA%\rizin\cutter\plugins\python` | none | `~/.local/opt/cutter-2.4.1/cutter.exe -A 0 <copy>`, then `rea list-cutter-sessions` and `rea cutter-command <id> <gen> <cmd>`. Close Cutter after. |
| objdump | GNU binutils 2.47 (MSYS2) | `REA_OBJDUMP_COMMAND` | `rea inspect-with-objdump <copy> file_headers`; also gives PE imports and exports, which 6.7.0 lacks natively. |
| WASM | WABT 1.0.42 | `REA_WABT_BIN_DIRECTORY` | `rea inspect-wasm-artifact <copy>` |
| .NET | ilspycmd 11.1.0.9782 | `REA_ILSPY_CMD_PATH` | `rea inspect-managed-artifact <copy>` |
| Android | jadx-headless-mcp 0.7.1, Apktool 3.0.3, adb 37.0.0 (copy of the winget Platform-Tools in `opt\platform-tools-37.0.0`) | `REA_JADX_MCP_JAR`, `REA_APKTOOL_COMMAND`, `REA_ADB_PATH` | `rea inspect-android-package`, `rea decode-android-resources`, `rea list-adb-devices`. `adb kill-server` when done. |
| Runtime | Frida 17.23.2 in the REA prefix | none | `rea list-frida-devices`, `list-frida-processes`. Never attach to system binaries, drivers or anything we did not build (hard rules above). |
| Packets | Wireshark 4.6.9 tshark/capinfos (unpacked, no Npcap) | `REA_TSHARK_COMMAND`, `REA_CAPINFOS_COMMAND` | `rea inspect-pcap-capture <file>`. The recorded-packet and mitmdump lanes are Linux only. |

Not on Windows: Kuna (no Windows build), Hopper (macOS), Wakaru (installed at `~/.local/opt/wakaru-1.14.0`, but REA 6.7.0 only drives it on Linux), the NativeAOT jar, GDB, pwndbg, pwntools, Binwalk/Unblob, sigrok. JEB: no account. `rea doctor` has checks only for Ghidra, IDA, JADX, ILSpy, Hopper and Kuna; the other lanes are proven by a real call each. Its overall `healthy: false` comes from Hopper, Kuna and the `rea setup` registrations, all skipped on purpose.

## Ubuntu probe stick

Live USB, no persistent install. Put Node from nodejs.org (the same major as the pin allows) under `~/.local/opt`, verify its published SHA-256, then run the same `npm pack` / sha256 check / `npm install --ignore-scripts --omit=optional` into `~/.local/opt/rea-agents-6.7.0`. Use it only for PE and Mach-O files copied onto the stick. The stick is a probe: no disk writes to the laptop's partitions, no mounting the ESP read-write. Linux has `objdump`, `readelf`, `strings` and `file` for the rest.

## Pins for other machines

Ghidra 12.1.4 (sha256 `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`, the macOS decompiler must be built locally from its bundled source) and Temurin JDK 21.0.13+9 (sha256 `9aa1d1c17ae5467a022679e7e0af5c00797d94ac462ed1a46f4db07a8a34a6dd`). See also the `decompile` skill, which covers Ghidra and radare2 on the Windows side.

## MCP

Registered at user scope on both sides (Bash, 2026-10-24). macOS: `claude mcp add --scope user rea -e REA_MCP_INPUT_SCHEMA_PROFILE=compact -- ~/.local/bin/rea mcp`. It goes through the wrapper, so the pin and the blocked commands hold. The catalog costs about 68k tokens with tool search off; with deferred tools it loads on demand. `claude mcp remove --scope user rea` takes it out. Prefer the CLI for one-off questions; the MCP suits long investigations.
