# Sprint 2 — Website Sync Completion (WooCommerce Push)

**Goal:** price changes on existing products go live on the website automatically; new products
land as `private` for manual review — the full loop, not just the BUSY-side half from Sprint 1.

**Depends on:** Sprint 1
**PRD references:** §5, `docs/reference` (none directly — this is prototype `13-sync-service.md`
logic, ported; if that file isn't in `docs/reference/`, pull it from `Busin/docs/13-sync-service.md`)

## Scope

- [x] Port `wooClient.js` → `app/integrations/woocommerce.py`
- [x] Port the **seed-mode safety net** exactly as designed in the prototype: first-ever sync
      must NOT bulk-create the whole catalog in WooCommerce without an explicit one-time opt-in.
      This was a deliberate design decision to avoid surprising the business — do not simplify
      it away. (Kept as a CLI script, `scripts/seed_import_woocommerce.py`, not an HTTP endpoint
      — there's still no auth system, see the Sprint 1 doc's flagged gap, and "bulk-create N
      live products" shouldn't be one unauthenticated call away.)
- [x] Category creation + reuse (create once, cache the WooCommerce category ID — don't create
      duplicates on every sync, this was verified behavior in the prototype)
- [x] Wire the Sprint 1 sync job to also push to WooCommerce after each successful BUSY pull
- [x] Config: WooCommerce site URL + REST API credentials (**dedicated API key, not an admin's**)
- [x] Admin visibility: `GET /api/v1/sync/status` extended to show last WooCommerce push result

## Out of scope

- Stock push (still blocked — see Sprint 1).
- Anything to do with orders/payments (Sprint 3+).

## Definition of Done

- [ ] A live test: change one product's price in the BUSY test company, run sync, confirm it
      updates live on a real (or sandbox) WooCommerce site within one sync cycle. **Not done** —
      same reason as the Sprint 0 live-BUSY check: no live BUSY host is reachable from this
      environment (`docs/sprints/sprint-00-foundations.md`), and no real/sandbox WooCommerce
      site credentials were provided either. Covered instead by
      `tests/domain/catalog/test_woo_sync.py::test_price_change_updates_only_the_changed_product`
      against the mock WooCommerce server — proves the logic, not the live integration.
- [ ] A live test: add a genuinely new item in BUSY, run sync **without** the seed-import flag on
      a fresh environment, confirm it does **not** appear in WooCommerce until the explicit
      opt-in is triggered. **Not done** for the same live-environment reason. Covered instead by
      `test_seed_mode_makes_zero_woocommerce_calls` (mock WooCommerce, asserts zero calls) and
      `test_seed_import_creates_products_and_dedups_category` (proves the flip works).
- [x] Category dedup verified: syncing two products in the same category creates exactly one
      WooCommerce category, not two.
      (`test_seed_import_creates_products_and_dedups_category`)
