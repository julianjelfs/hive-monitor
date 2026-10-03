#!/usr/bin/env bash
# Nightly snapshot of the monitor's database, taken on the Pi. It holds the device keys
# Hive remembers this Pi by; losing them means another SMS code, nothing worse.
set -euo pipefail

DB="${HIVE_DB_PATH:-/home/julian_jelfs/hive-monitor/backend/hive.db}"
DEST="${HIVE_BACKUP_DIR:-/home/julian_jelfs/hive-backups}"
KEEP=14

mkdir -p "$DEST"
out="$DEST/hive-$(date +%Y%m%d-%H%M%S).db"

# SQLite's online backup API copies a consistent snapshot while the monitor keeps running.
python3 - "$DB" "$out" <<'PY'
import sqlite3
import sys

src, dst = sys.argv[1], sys.argv[2]
source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
target = sqlite3.connect(dst)
with target:
    source.backup(target)

state = target.execute("PRAGMA integrity_check").fetchone()[0]
keys = target.execute("select count(*) from kv where key = 'hive_device'").fetchone()[0]
target.close()
source.close()

if state != "ok":
    raise SystemExit(f"integrity check failed: {state}")
if keys == 0:
    raise SystemExit("backup holds no Hive device keys; has setup been run?")
print("backed up")
PY

echo "wrote $out ($(du -h "$out" | cut -f1))"
ls -1t "$DEST"/hive-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "keeping $(ls -1 "$DEST"/hive-*.db 2>/dev/null | wc -l | tr -d ' ') backups in $DEST"
