# Sprint 1 — BUSY Read Layer + Incremental Sync (Catalog)

**Goal:** products, categories, and material centers sync from BUSY into MySQL,
incrementally, provably (repeat the "17.3s full → 2.2s no-op" proof from the prototype, in Python).

**Depends on:** Sprint 0
**PRD references:** §5, §9 (Migration Plan), §11 (Scale Planning)

## Scope

- [ ] MySQL schema: `products`, `categories`, `material_centers`, `sync_state` (per PRD §5's data model)
- [ ] Port the `Stamp`-checkpoint mechanism from `catalogSync.js` (`get_last_stamp`/`set_last_stamp`) — same design, same `is_active`-not-delete rule (a real bug fix from the prototype — don't reintroduce it)
- [ ] **Pagination from day one** — do NOT port the prototype's single unbounded query as-is. Even though the test company was small enough not to need it, PRD §11 already flags this as a retail-scale requirement. Window by `Stamp` ranges or `TOP N`, loop until exhausted.
- [ ] Real Item field mapping — `SalePrice`, `MainUnit`, `ParentGroup`, `DoNotMaintainStkBal` (confirmed real names, see `docs/reference/12-schema-findings.md` — do not re-guess these)
- [ ] `GET /api/v1/products`, `/api/v1/products/{code}`, `/api/v1/categories`, `/api/v1/material-centers`
- [ ] `POST /api/v1/sync/products` (admin-only, `{"full": bool}`), `GET /api/v1/sync/status`
- [ ] A scheduled/background trigger for incremental sync (interval configurable; this is the seed of the eventual worker, doesn't need to be the full outbox system yet)

## Out of scope

- Stock quantity — still an unsolved problem (PRD §5 note, `12-schema-findings.md` §4). Do not fabricate a stock number.
- WooCommerce push (Sprint 2).
- Item generic-column decoding for bulk fetching — only revisit if/when the catalog actually reaches a size where per-item `GetMasterXML` calls become the bottleneck (see PRD §11).

## Definition of Done

- [ ] First full sync and an immediate re-sync are both timed and logged — the second must show
      near-zero BUSY calls (mirroring the prototype's proof). This is a **required**, not
      optional, verification step before closing this sprint.
- [ ] A record going blocked/deactivated in BUSY results in `is_active=false` locally, not a
      silently stale row and not a deleted row.
- [ ] Pagination verified against a query returning more rows than one page size, in a test.
- [ ] No endpoint in this sprint ever calls BUSY synchronously inside a request — all BUSY calls
      happen in the scheduled sync job; API endpoints only ever read MySQL.
