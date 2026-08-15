# Sprint 1 — BUSY Read Layer + Incremental Sync (Catalog)

**Goal:** products, categories, and material centers sync from BUSY into MySQL,
incrementally, provably (repeat the "17.3s full → 2.2s no-op" proof from the prototype, in Python).

**Depends on:** Sprint 0
**PRD references:** §5, §9 (Migration Plan), §11 (Scale Planning)

## Scope

- [x] MySQL schema: `products`, `categories`, `material_centers`, `sync_state` (per PRD §5's data model)
- [x] Port the `Stamp`-checkpoint mechanism from `catalogSync.js` (`get_last_stamp`/`set_last_stamp`) — same design, same `is_active`-not-delete rule (a real bug fix from the prototype — don't reintroduce it)
- [x] **Pagination from day one** — do NOT port the prototype's single unbounded query as-is. Even though the test company was small enough not to need it, PRD §11 already flags this as a retail-scale requirement. Window by `Stamp` ranges or `TOP N`, loop until exhausted. (Implemented as compound `(Stamp, Code)` keyset pagination, not plain `Stamp`-only — real `Stamp` values are coarse enough per CLAUDE.md §8 that a plain-Stamp cursor can skip or infinite-loop on ties; see `app/busy/pagination.py`.)
- [x] Real Item field mapping — `SalePrice`, `MainUnit`, `ParentGroup`, `DoNotMaintainStkBal` (confirmed real names, see `docs/reference/12-schema-findings.md` — do not re-guess these)
- [x] `GET /api/v1/products`, `/api/v1/products/{code}`, `/api/v1/categories`, `/api/v1/material-centers`
- [ ] `POST /api/v1/sync/products` (**admin-only**, `{"full": bool}`), `GET /api/v1/sync/status` — endpoints exist and work (never call BUSY inline), but **"admin-only" is not implemented**: there is no auth/access-control scheme anywhere yet in this codebase or the PRD to build against, and inventing one unprompted felt like the wrong call. Anyone who can reach the API can currently trigger a sync. Flagging rather than silently skipping or silently guessing an auth scheme — needs a decision (Sprint 5 hardening, or earlier?) on what "admin-only" actually means here (API key? internal network only? real auth?).
- [x] A scheduled/background trigger for incremental sync (interval configurable; this is the seed of the eventual worker, doesn't need to be the full outbox system yet) — off by default per-process (`CATALOG_SYNC_ENABLED`), so scaling the API to multiple workers doesn't multiply sync frequency; the manual trigger endpoint works regardless.

## Out of scope

- Stock quantity — still an unsolved problem (PRD §5 note, `12-schema-findings.md` §4). Do not fabricate a stock number.
- WooCommerce push (Sprint 2).
- Item generic-column decoding for bulk fetching — only revisit if/when the catalog actually reaches a size where per-item `GetMasterXML` calls become the bottleneck (see PRD §11).

## Definition of Done

**Live validation, 2026-08-15** (beyond this DoD's original mock-only bar — BUSY became
reachable from the dev environment after this sprint was first closed; see
`docs/sprints/sprint-00-foundations.md`): `run_catalog_sync(full=True)` against the real
BUSY company synced 2 real Material Centers and 8 real products with zero failures in
~11s total, correctly mapping real field names and `DoNotMaintainStkBal` (service items
vs. physical Cable items), and correctly skipped the WooCommerce push (not configured)
rather than failing. Confirms Sprint 1 works end-to-end against production data, not
just the mock.

- [x] First full sync and an immediate re-sync are both timed and logged — the second must show
      near-zero BUSY calls (mirroring the prototype's proof). This is a **required**, not
      optional, verification step before closing this sprint. (`tests/domain/catalog/test_scheduler.py`
      — full sync finds 8/2 changed rows, immediate re-sync finds 0/0, both timed via
      `elapsed=%.2fs` log lines.)
- [x] A record going blocked/deactivated in BUSY results in `is_active=false` locally, not a
      silently stale row and not a deleted row. (`tests/domain/catalog/test_sync.py::test_sync_products_paginates_and_marks_blocked_item_inactive`)
- [x] Pagination verified against a query returning more rows than one page size, in a test.
      (`tests/busy/test_pagination.py` — 8 rows, page_size=3, with a 4-way `Stamp` tie spanning
      a page boundary; also exercised again at the domain level in `test_sync.py`.)
- [x] No endpoint in this sprint ever calls BUSY synchronously inside a request — all BUSY calls
      happen in the scheduled sync job; API endpoints only ever read MySQL.
      (`tests/api/test_catalog_routes.py::test_trigger_products_sync_hands_off_to_background_tasks_not_inline`
      proves the route hands off to `BackgroundTasks` rather than awaiting the sync inline.)
