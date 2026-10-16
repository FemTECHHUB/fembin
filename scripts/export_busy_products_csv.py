#!/usr/bin/env python3
"""Pull every Item (MasterType=6) straight from a BUSY install and dump busy_code, name,
print_name, and price to a CSV file — raw, no cleanup/dedup/mapping. Standalone: does not
touch our local MySQL mirror or any of the sync checkpoints in app/domain/catalog/sync.py,
so it's safe to point at a BUSY install other than the one configured in .env (a new
client's server, a different IP, different login) without disturbing this app's own state.

`name` and `print_name` are NOT always the same thing — confirmed live 2026-10-15 against
a second BUSY install (3.131.207.45): `Name` is often an internal SKU-style string (e.g.
"Solar Panel-150wt") while `PrintName` is the real customer-facing description (e.g. "150
Watt Mono Solar Panel"). (On the *other* BUSY install this app normally talks to,
PrintName was checked and found to just mirror Name on every item — CLAUDE.md §8 — so
don't assume either direction; this script always pulls both.)

Two BUSY calls per item, same pattern as app/domain/catalog/sync.py's sync_products:
one bulk query for the code list, then one GetMasterXML per item for its real
Name/PrintName/SalePrice (none of these are in the bulk Master1 columns). Detail calls run
in small concurrent batches (--concurrency) rather than one at a time — plain sequential
with a per-item delay was too slow on a 14k-item catalog (~70 minutes). A failed detail
call for one item is retried a couple of times (BUSY's session is known to drop
unpredictably, CLAUDE.md §8) and then logged and skipped — it never aborts the whole
export.

Resumable: re-running with the same --output skips any busy_code already written there
and only fetches what's missing — safe to re-run after an interrupted large export
without re-pulling everything from scratch. Pass --fresh to start over instead.

Usage:
    # Test against the BUSY host already configured in .env (default: this repo's
    # BUSY_HOST/PORT/USERNAME/PASSWORD):
    uv run python scripts/export_busy_products_csv.py

    # Point at a different BUSY install entirely — nothing here is read from .env:
    uv run python scripts/export_busy_products_csv.py \
        --host 203.0.113.9 --port 981 --username someuser --password 'secret' \
        --output exports/client_x_products.csv
"""

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.busy.client import BusyClient, BusyError
from app.busy.constants import MasterType
from app.busy.xml_util import parse_element_xml, parse_rowset_xml
from app.config import get_settings
from app.logging_config import setup_logging

logger = logging.getLogger("scripts.export_busy_products_csv")

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "exports"


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=settings.busy_host, help="BUSY host/IP (default: .env BUSY_HOST)")
    parser.add_argument("--port", type=int, default=settings.busy_port, help="BUSY port (default: .env BUSY_PORT)")
    parser.add_argument("--username", default=settings.busy_username, help="BUSY username (default: .env BUSY_USERNAME)")
    parser.add_argument("--password", default=settings.busy_password, help="BUSY password (default: .env BUSY_PASSWORD)")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=f"CSV output path (default: {DEFAULT_OUTPUT_DIR}/busy_products_<host>_<timestamp>.csv)",
    )
    parser.add_argument(
        "--timeout", type=float, default=settings.busy_timeout_seconds, help="Per-request timeout in seconds"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="How many items' detail calls to run at once (default: 8). Higher is faster "
        "but puts more simultaneous load on BUSY, which is one instance with no proven "
        "concurrent-request resilience (CLAUDE.md §8) and may be serving real live "
        "traffic. Raise gradually (e.g. 16, 24) rather than jumping straight to a huge "
        "number on a BUSY install you haven't tested against before.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.2,
        help="Pause between each batch of --concurrency items (default: 0.2s) — a small "
        "courtesy gap so this stays a controlled burst, not a flood.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="Log a progress line every N items (default: 50)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries for a single item's detail call before giving up on it (default: 2) "
        "— BUSY's session is known to drop unpredictably (CLAUDE.md §8), so one transient "
        "timeout shouldn't cost that item its row.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any existing file at --output and start over, instead of resuming "
        "(skipping codes already written there).",
    )
    return parser.parse_args()


async def _fetch_item_codes(client: BusyClient) -> list[tuple[int, str]]:
    """Bulk pull every Item's Code + Name (no Stamp filtering — this is a one-shot full
    export, not an incremental sync)."""
    xml = await client.run_query(
        f"SELECT Code, Name FROM Master1 WHERE MasterType = {int(MasterType.ITEM)}"
    )
    rows = parse_rowset_xml(xml)
    return [(int(row["Code"]), str(row.get("Name", ""))) for row in rows]


def _load_already_done(output_path: Path) -> set[int]:
    """Codes already written to a prior (possibly interrupted) run of this same output
    file — resume skips these rather than re-fetching them. A code only ever lands here
    on success, so a crashed/failed item is naturally retried on the next run without any
    separate failed-items bookkeeping."""
    if not output_path.exists():
        return set()
    with output_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {int(row["busy_code"]) for row in reader}


@dataclass(frozen=True)
class ItemDetail:
    name: str
    print_name: str
    price: Decimal


async def _fetch_detail(client: BusyClient, code: int, *, retries: int) -> ItemDetail | None:
    """One GetMasterXML call for this item's live Name/PrintName/SalePrice — returns None
    on failure so the caller can tell "couldn't read it" apart from a genuine value.

    Retries transient network/timeout errors a few times before giving up on this one
    item — BUSY's session is known to drop unpredictably (CLAUDE.md §8), and a thousands-
    of-items export will hit that at least once. `BusyError` (BUSY itself returned
    Result="F" for this specific item) is not retried — that's a definite answer, not a
    transient blip, so retrying would just waste time re-asking the same question."""
    for attempt in range(retries + 1):
        try:
            detail_xml = await client.get_master_xml(code)
            break
        except BusyError as exc:
            logger.warning("GetMasterXML failed for item %s: %s", code, exc)
            return None
        except httpx.HTTPError as exc:
            if attempt == retries:
                logger.warning(
                    "GetMasterXML network error for item %s after %d attempt(s): %s",
                    code,
                    attempt + 1,
                    exc,
                )
                return None
            backoff = 2.0 * (attempt + 1)
            logger.warning(
                "GetMasterXML network error for item %s (attempt %d/%d), retrying in %.0fs: %s",
                code,
                attempt + 1,
                retries + 1,
                backoff,
                exc,
            )
            await asyncio.sleep(backoff)

    parsed = parse_element_xml(detail_xml)
    node = parsed.get("Item", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(node, dict):
        logger.warning("item %s: unexpected GetMasterXML shape", code)
        return None
    return ItemDetail(
        name=str(node.get("Name", "")),
        print_name=str(node.get("PrintName", "")),
        price=Decimal(str(node.get("SalePrice") or 0)),
    )


async def _run(args: argparse.Namespace) -> Path:
    output_path = args.output
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"busy_products_{args.host}_{timestamp}.csv"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    already_done = set() if args.fresh else _load_already_done(output_path)
    if already_done:
        logger.info(
            "resuming %s — %d codes already present, will skip them", output_path, len(already_done)
        )

    async with BusyClient(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        timeout_seconds=args.timeout,
    ) as client:
        logger.info("connecting to BUSY at %s:%s as %r", args.host, args.port, args.username)
        items = await _fetch_item_codes(client)
        total = len(items)
        todo = [(code, name) for code, name in items if code not in already_done]
        remaining = len(todo)
        est_batches = -(-remaining // args.concurrency)  # ceil
        logger.info(
            "found %d items (%d remaining) — fetching in batches of %d, %.1fs between "
            "batches (est. %.0fs remaining)",
            total,
            remaining,
            args.concurrency,
            args.delay_seconds,
            est_batches * args.delay_seconds,
        )

        write_header = not (already_done and output_path.exists())
        written = 0
        failed = 0
        done_now = 0
        last_logged = 0
        with output_path.open("a" if already_done else "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["busy_code", "name", "print_name", "price"])
                f.flush()

            for batch_start in range(0, remaining, args.concurrency):
                batch = todo[batch_start : batch_start + args.concurrency]
                details = await asyncio.gather(
                    *(_fetch_detail(client, code, retries=args.retries) for code, _ in batch)
                )
                for (code, name), detail in zip(batch, details):
                    if detail is None:
                        failed += 1
                    else:
                        writer.writerow([code, name, detail.print_name, detail.price])
                        written += 1
                # Flush after every batch (not just at the end) so a crash/interrupt
                # partway through a large export still leaves everything pulled so far
                # on disk, not buffered in memory and lost.
                f.flush()
                done_now += len(batch)

                is_last_batch = batch_start + len(batch) >= remaining
                if done_now - last_logged >= args.progress_every or is_last_batch:
                    logger.info(
                        "progress: %d/%d (written=%d failed=%d)",
                        done_now,
                        remaining,
                        written,
                        failed,
                    )
                    last_logged = done_now

                if not is_last_batch:
                    await asyncio.sleep(args.delay_seconds)

    logger.info(
        "export done: written=%d failed=%d (plus %d already done from a prior run) -> %s",
        written,
        failed,
        len(already_done),
        output_path,
    )
    return output_path


def main() -> None:
    args = _parse_args()
    setup_logging(get_settings().log_level)
    # One httpx INFO line per item would flood the log across a thousand-item export —
    # our own progress line (--progress-every) is the signal to watch instead.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
