#!/bin/bash
# Pull every Item (MasterType=6) straight from a BUSY install via plain curl — no Python,
# no venv — and write busy_code,name,print_name,price to a CSV. Same two-calls-per-item
# shape as scripts/export_busy_products_csv.py (one bulk Code/Name query, SC=1, then one
# GetMasterXML detail call per item, SC=9, for PrintName/SalePrice — neither is in the
# bulk columns). Resumable: re-running with the same OUTPUT skips codes already written.
#
# Usage:
#   ./scripts/export_busy_products_curl.sh HOST PORT USERNAME PASSWORD OUTPUT.csv
#
# Example:
#   ./scripts/export_busy_products_curl.sh 3.131.207.45 981 Femtech '@demo123' \
#       exports/3.131.207.45_products.csv
#
# Tunables (env vars, all optional):
#   CONCURRENCY=8   how many detail calls to run at once (default 8)
#   DELAY=0.2       pause between batches in seconds (default 0.2)
#   RETRIES=2       retries for one item's detail call before giving up on it (default 2)
#   PROGRESS_EVERY=50
set -uo pipefail

HOST="${1:?Usage: $0 HOST PORT USERNAME PASSWORD OUTPUT.csv}"
PORT="${2:?Usage: $0 HOST PORT USERNAME PASSWORD OUTPUT.csv}"
USERNAME="${3:?Usage: $0 HOST PORT USERNAME PASSWORD OUTPUT.csv}"
PASSWORD="${4:?Usage: $0 HOST PORT USERNAME PASSWORD OUTPUT.csv}"
OUTPUT="${5:?Usage: $0 HOST PORT USERNAME PASSWORD OUTPUT.csv}"

CONCURRENCY="${CONCURRENCY:-8}"
DELAY="${DELAY:-0.2}"
RETRIES="${RETRIES:-2}"
PROGRESS_EVERY="${PROGRESS_EVERY:-50}"

BASE_URL="http://$HOST:$PORT/"
mkdir -p "$(dirname "$OUTPUT")"

# BUSY's numeric XML entities (CLAUDE.md §8 — real data has these, not just the 5 named
# XML entities) plus the named ones, decoded before we re-escape for CSV.
decode_entities() {
    sed -e 's/&amp;/\&/g' -e "s/&#39;/'/g" -e "s/&#x27;/'/g" \
        -e 's/&quot;/"/g' -e 's/&lt;/</g' -e 's/&gt;/>/g'
}

echo "connecting to BUSY at $HOST:$PORT as $USERNAME" >&2
bulk_headers=$(curl -s -D - -o /tmp/busy_bulk_body.$$ -G "$BASE_URL" \
    -H "UserName: $USERNAME" -H "Pwd: $PASSWORD" \
    -H "SC: 1" -H "Qry: SELECT Code, Name FROM Master1 WHERE MasterType = 6")
bulk_xml=$(cat /tmp/busy_bulk_body.$$)
rm -f /tmp/busy_bulk_body.$$

if [[ -z "$bulk_xml" ]]; then
    result=$(printf '%s' "$bulk_headers" | grep -i "^Result:" | tr -d '\r')
    description=$(printf '%s' "$bulk_headers" | grep -i "^Description:" | cut -d: -f2- | sed 's/^ *//;s/\r$//')
    if [[ -n "$description" ]]; then
        # BUSY answered but rejected the operation itself — e.g. "Please open a company
        # in BUSY before a valid operation" (CLAUDE.md §8: the company-open session on
        # the BUSY desktop app drops unpredictably — this is BUSY's real state, not a
        # bug in this script). Someone needs to open the company on that BUSY install.
        echo "ERROR: BUSY rejected the query ($result): $description" >&2
    else
        echo "ERROR: empty response from BUSY for the bulk item query — check host/port/login/firewall" >&2
    fi
    exit 1
fi

# "<z:row Code='1541' Name='Solar Panel-150wt'/>" -> "1541<TAB>Solar Panel-150wt"
mapfile -t pairs < <(printf '%s\n' "$bulk_xml" | \
    sed -n "s/.*<z:row Code='\([0-9]\+\)' Name='\([^']*\)'.*/\1\t\2/p")
total=${#pairs[@]}
if [[ "$total" -eq 0 ]]; then
    echo "ERROR: found 0 items — the bulk query matched nothing (bad login, or BUSY returned an error — check for a Result/Description issue)" >&2
    exit 1
fi

# Resume: codes already written to OUTPUT from a prior (possibly interrupted) run.
# (Tracking count in a plain counter, not `${#already_done[@]}` — an empty associative
# array trips "unbound variable" under `set -u` on this bash, even freshly declared.)
declare -A already_done
resume_count=0
if [[ -f "$OUTPUT" ]]; then
    while IFS=, read -r code _rest; do
        [[ "$code" == "busy_code" ]] && continue
        already_done["$code"]=1
        resume_count=$((resume_count + 1))
    done < "$OUTPUT"
fi
if [[ "$resume_count" -gt 0 ]]; then
    echo "resuming $OUTPUT — $resume_count codes already present, will skip them" >&2
else
    echo "busy_code,name,print_name,price" > "$OUTPUT"
fi

echo "found $total items — fetching in batches of $CONCURRENCY, ${DELAY}s between batches" >&2

# One item's detail call -> one ready-to-append CSV line on stdout (nothing on failure,
# after $RETRIES attempts) — BUSY's session is known to drop unpredictably (CLAUDE.md
# §8), so a transient failure is retried with backoff rather than aborting the item.
fetch_detail() {
    local code="$1" name="$2" xml attempt=0

    while true; do
        xml=$(curl -s --max-time 30 "$BASE_URL" \
            -H "UserName: $USERNAME" -H "Pwd: $PASSWORD" \
            -H "SC: 9" -H "MasterCode: $code")
        [[ -n "$xml" ]] && break
        attempt=$((attempt + 1))
        if [[ "$attempt" -gt "$RETRIES" ]]; then
            echo "GetMasterXML failed for item $code after $attempt attempt(s)" >&2
            return
        fi
        sleep "$((attempt * 2))"
    done

    local print_name price
    print_name=$(printf '%s' "$xml" | grep -oP '<PrintName>\K[^<]*' | head -1 | decode_entities)
    price=$(printf '%s' "$xml" | grep -oP '<SalePrice>\K[^<]*' | head -1)
    price="${price:-0}"
    name=$(printf '%s' "$name" | decode_entities | sed -e 's/"/""/g')
    print_name=$(printf '%s' "${print_name:-}" | sed -e 's/"/""/g')
    printf '%s,"%s","%s",%s\n' "$code" "$name" "$print_name" "$price"
}
export -f fetch_detail decode_entities
export BASE_URL USERNAME PASSWORD RETRIES

written=0
failed=0
done_now=0
for ((start = 0; start < total; start += CONCURRENCY)); do
    batch=("${pairs[@]:start:CONCURRENCY}")
    batch_input=()
    for pair in "${batch[@]}"; do
        code="${pair%%$'\t'*}"
        [[ -n "${already_done[$code]:-}" ]] && continue
        batch_input+=("$pair")
    done
    [[ "${#batch_input[@]}" -eq 0 ]] && continue

    # Flushed per batch, not buffered to the end — a crash/interrupt partway through a
    # large export still leaves everything pulled so far on disk.
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        printf '%s\n' "$line" >> "$OUTPUT"
        written=$((written + 1))
    done < <(
        printf '%s\n' "${batch_input[@]}" | xargs -P "$CONCURRENCY" -d '\n' -I{} bash -c '
            pair="{}"
            code="${pair%%$'"'"'\t'"'"'*}"
            name="${pair#*$'"'"'\t'"'"'}"
            fetch_detail "$code" "$name"
        '
    )

    done_now=$((done_now + ${#batch_input[@]}))
    if (( done_now % PROGRESS_EVERY < CONCURRENCY )); then
        echo "progress: ~$done_now/$total done (written=$written)" >&2
    fi
    sleep "$DELAY"
done

echo "export done: written=$written -> $OUTPUT" >&2
