"""One-off (2026-10-14): migrated notes were written by a build that ignored verified_on/origin.

Restores each note's real verification date and review date, and labels its log rows as migration.
Reads [{note_id, verified_at, review_by}] JSON on stdin. Run as the service user:
    sudo -u memory-mcp /srv/memory-mcp/venv/bin/python fix_migration_dates.py < fixes.json
"""
import json
import sqlite3
import sys

fixes = json.load(sys.stdin)
con = sqlite3.connect("/srv/memory-mcp/data/memory.sqlite3", timeout=60)
with con:
    con.execute("BEGIN IMMEDIATE")
    meta = changes = 0
    for f in fixes:
        meta += con.execute("UPDATE note_meta SET verified_at=?,review_by=?,origin='migration' WHERE note_id=?",
                            (f["verified_at"], f["review_by"], f["note_id"])).rowcount
        changes += con.execute("UPDATE changes SET op='migrate',surface='migration' WHERE note_id=? AND op='create'",
                               (f["note_id"],)).rowcount
print(json.dumps({"notes_fixed": meta, "change_rows_relabelled": changes, "expected": len(fixes)}))
