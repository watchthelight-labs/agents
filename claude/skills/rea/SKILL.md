---
name: rea
description: Project Legion reverse engineering with a pinned, audited REA (morluto/rea) CLI plus the native macOS tools. Use for Mach-O and dyld shared cache frameworks (QuartzCore and friends), Apple GPU bundles and kexts, IOKit user-client selector mapping, NVIDIA and Intel Windows driver files (.sys, .dll, .inf), and OpenCore binaries. Trigger: /rea, "reverse this driver", "what does this kext export", "map the IOKit selectors", "inspect this PE". Read-only on system binaries.
---

# REA for Project Legion

Adapted from the `reverse-engineer-anything` skill of [morluto/rea](https://github.com/morluto/rea) (MIT, Copyright (c) 2026 morluto; notice in `licenses/rea-MIT.txt` of the agents repo). Checked 2026-10-24 against rea-agents 6.7.0. The upstream text moves daily; re-run the audit before changing the pin.

## What REA is here, and what it is not

REA is a Node CLI (`rea <command>`) with an MCP server around it. We use the CLI only, pinned to **rea-agents 6.7.0** (tarball sha256 `20958a66dba1a011e50a486beb9463a343128ed368c984f94065362c13f51f90`, npm sha512 `yhIx2ioJYYT1C/tONfYeitC6LhnKmCh+ZwRUOgYuhSc733lGhkkt73zhug9WmLgxoMdKuqIYGCoBfD4fXkOhFw==`), installed with `--ignore-scripts --omit=optional` into a private prefix. The audit is `research/repository-audits/rea.md` in the project repo.

REA has **no support** for the dyld shared cache, kexts (`MH_KEXT_BUNDLE`), kernelcaches or `MH_FILESET`, or IOKit analysis. It does not resolve `/System` libraries (they live in the cache). Its native decompilation drives Ghidra, Hopper or IDA, and none is installed here (Ghidra 12.1.4 and Temurin JDK 21 are pinned in the audit but wait for Bash's OK). So REA is used for the parts it does well without a provider, and the macOS tools do the rest.

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
- No JDK, Ghidra or Hopper. Do not install them without Bash's OK.

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

Windows C: is mounted read-only at `/Volumes/Untitled`. Copy the file out first, then `rea inspect-pe-resources`, `rea inspect-artifact`, `llvm-objdump-mp-20 -p` (PE headers, import and export tables), `strings`. Decompiling a `.sys` needs a provider; wait for the Ghidra OK.

## Windows session (PowerShell, C:\Users\Hackintosh)

The same pinned package works there, and it is the main place the fake REA zips will turn up: take REA only from `npm rea-agents`, `morluto/rea` or rea.tools. Because the Windows package carries a prebuilt addon (`native/windows/build/rea-windows-x64.node`, MinGW-w64, not examined in the audit), ask Bash before the first Windows install.

```powershell
node -v    # needs the range in the audit, 22.19 or newer 24.x
mkdir $HOME\tools\rea -Force; cd $HOME\tools\rea
npm pack rea-agents@6.7.0 --ignore-scripts
(Get-FileHash rea-agents-6.7.0.tgz -Algorithm SHA256).Hash   # must equal 20958a66dba1a011e50a486beb9463a343128ed368c984f94065362c13f51f90
npm install --ignore-scripts --omit=optional --no-audit --no-fund .\rea-agents-6.7.0.tgz
node .\node_modules\rea-agents\scripts\rea.mjs --version     # 6.7.0
```

Run it by that path (no `-g`, no `npx`, no `rea setup`). Work on copies of `.sys`/`.dll` files outside `C:\Windows`. Driver files in the driver store are signed and in use; copy, do not edit. PowerShell is already Administrator on this machine, so add no elevation steps. Windows Ghidra is REA's experimental lane; not installed.

## Ubuntu probe stick

Live USB, no persistent install. Put Node from nodejs.org (the same major as the pin allows) under `~/.local/opt`, verify its published SHA-256, then run the same `npm pack` / sha256 check / `npm install --ignore-scripts --omit=optional` into `~/.local/opt/rea-agents-6.7.0`. Use it only for PE and Mach-O files copied onto the stick. The stick is a probe: no disk writes to the laptop's partitions, no mounting the ESP read-write. Linux has `objdump`, `readelf`, `strings` and `file` for the rest.

## Not installed yet (need Bash's OK, pinned in the audit)

Ghidra 12.1.4 (sha256 `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`, the macOS decompiler must be built locally from its bundled source) and Temurin JDK 21.0.13+9 (sha256 `9aa1d1c17ae5467a022679e7e0af5c00797d94ac462ed1a46f4db07a8a34a6dd`). See also the `decompile` skill, which covers Ghidra and radare2 on the Windows side.

## MCP

The REA MCP server is not registered. Its tool catalog is large (tens of thousands of tokens) and registering it edits `~/.claude.json`. If Bash wants it, the exact command is in `docs/rea.md` of the project repo.
