#!/bin/bash
# Drains the outbox roughly every 3 seconds for ~55s, then exits just before the next
# cron minute tick fires a fresh instance. Meant to be run from cron wrapped in `flock`
# (see DEPLOYMENT.md / progress.md) so exactly one instance is ever running — required
# because VchNo is computed sequentially, one job at a time (app/domain/orders/
# quotations.py) and is not safe under concurrent drainers.
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/femtecha/virtualenv/busyapi.femtechaccess.com.ng/3.11/bin/activate

end=$((SECONDS + 55))
while [ "$SECONDS" -lt "$end" ]; do
    python scripts/drain_outbox_once.py
    sleep 3
done
