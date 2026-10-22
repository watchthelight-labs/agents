"""Consistent daily SQLite snapshots, atomically replacing the previous snapshots."""
from pathlib import Path
import shutil
import sqlite3

root = Path("/srv/memory-mcp/data")
destination = root / "backups"
destination.mkdir(mode=0o700, exist_ok=True)
# The vault snapshot holds ciphertext only; its key lives in /etc/memory-mcp.env.
for name in ("memory.sqlite3", "oauth.sqlite3", "vault.sqlite3"):
    source = root / name
    if not source.exists():
        continue
    if shutil.disk_usage(root).free < source.stat().st_size + 512 * 1024 * 1024:
        raise RuntimeError("Insufficient free space for a safe database snapshot")
    stem = "latest" if name == "memory.sqlite3" else name.removesuffix(".sqlite3") + "-latest"
    temp = destination / (stem + ".sqlite3.tmp")
    with sqlite3.connect(source) as src, sqlite3.connect(temp) as dst:
        src.backup(dst, pages=256, sleep=0.1)
        if dst.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError(f"{name} snapshot failed integrity check; previous backup retained")
    temp.replace(destination / (stem + ".sqlite3"))
    print(f"Consistent {name} snapshot saved.")
