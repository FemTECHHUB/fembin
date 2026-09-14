#!/bin/bash
# Re-syncs the catalog with a 5s rest between passes, for ~55s, then exits just before
# the next cron minute tick fires a fresh instance. Meant to be run from cron wrapped in
# `flock` so overlapping runs can't pile up if a pass runs long (e.g. BUSY is slow).
# Safe to run redundantly/concurrently even without the lock — catalog sync only
# upserts by busy_code (read from BUSY, write local mirror), no outbox-style
# sequential-numbering constraint — but flock keeps log output and BUSY load sane.
#
# NOTE on scale: CATALOG_SYNC_PRODUCTS_STRATEGY=full means every pass does a full
# Master1 re-pull *plus one GetMasterXML call per item*. At today's catalog size
# (~9 items, ~4s/pass) a 5s rest gives an actual cadence of ~9-10s end-to-end, not a
# literal 5s. On a much larger catalog (more material centers/items, per the plan to
# plug this into other BUSY installs) a full pass could take much longer than 5s itself,
# making this interval unrealistic and putting sustained load on BUSY — if that happens,
# switch CATALOG_SYNC_PRODUCTS_STRATEGY to "reconcile" (CLAUDE.md §8) rather than
# tightening this further.
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/femtecha/virtualenv/busyapi.femtechaccess.com.ng/3.11/bin/activate

end=$((SECONDS + 55))
while [ "$SECONDS" -lt "$end" ]; do
    python scripts/run_catalog_sync_once.py
    sleep 5
done
