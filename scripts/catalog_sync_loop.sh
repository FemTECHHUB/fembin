#!/bin/bash
# Re-syncs the catalog roughly every 30 seconds for ~55s, then exits just before the
# next cron minute tick fires a fresh instance. Meant to be run from cron wrapped in
# `flock` so overlapping runs can't pile up if a pass runs long (e.g. BUSY is slow).
# Safe to run redundantly/concurrently even without the lock — catalog sync only
# upserts by busy_code (read from BUSY, write local mirror), no outbox-style
# sequential-numbering constraint — but flock keeps log output and BUSY load sane.
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/femtecha/virtualenv/busyapi.femtechaccess.com.ng/3.11/bin/activate

end=$((SECONDS + 55))
while [ "$SECONDS" -lt "$end" ]; do
    python scripts/run_catalog_sync_once.py
    sleep 30
done
