# 13 — Production sync service: BUSY → WooCommerce

`code/busy-probe/src/syncService.js` — the first production piece. Auto-updates prices/stock
live, and pushes new products to WooCommerce as **private** for manual review, with category.

## What it does

| Situation | Behaviour |
|---|---|
| Existing product, price or stock changed in BUSY | **Updates live in WooCommerce immediately** — no review |
| Item never seen before | **Creates in WooCommerce as `private`** (configurable), with category — awaits manual publish |
| Nothing changed | Skipped — no API calls at all (cheap `Stamp`-based check) |

## ⭐ First-run safety net

The first time this runs, most/all items look "new." Rather than silently bulk-creating your
entire catalog as private products, it stays in **seed mode**: it records what it sees but makes
**zero WooCommerce calls** — until you explicitly run once with `--seed-import`. That's a
**one-time, permanent opt-in** (saved in `state.json`); after that, every genuinely new item is
created automatically, forever, exactly as intended.

```bash
npm run sync:once           # safe — seeds state only, no WooCommerce writes yet
npm run sync:once           # run again any time — still seed mode, idempotent
npm run sync:seed-import    # explicit go-ahead: pushes the existing backlog live (as private)
npm run sync:once           # from now on, only real changes are processed
npm run sync                # loop forever on cfg.sync.intervalMinutes
```

## Tested (offline, against mocks — see `src/mock-busy.js` / `src/mock-woo.js`)

1. First runs → seed mode, 0 WooCommerce calls, idempotent across repeats.
2. `--seed-import` → flips permanently, creates real products (`private`, correct SKU/price/stock),
   creates the category once and **reuses it** (no duplicates) across items in the same group.
3. Unchanged items on later runs → skipped, 0 calls (Stamp-based).
4. A real price change → exactly **one** live update call, only for the changed item; untouched
   items stay skipped.

## What's needed before this can run for real

- ☐ **WooCommerce site URL + REST API keys** (Settings → Advanced → REST API — give it its own
  Read/Write key, don't reuse an admin's). Fill into `config.json`'s `woo` block.
- ☐ **Confirm the real Item field names.** `mapItemFields()` in `syncService.js` currently guesses
  at a few plausible tag names (`Price`/`SalePrice`, `Stock`/`ClosingStock`) since we haven't seen
  a real `GetMasterXML` response for an Item yet (session dropped before we could check). This is
  the **one function** to fix once reconnected — everything else is verified.
- ☐ **Deploy to the VPS** (not your laptop) so it runs continuously — see `08-windows-deployment.md`
  for the whitelisting pattern; same idea applies to wherever the VPS is provisioned.
- ☐ Decide `sync.intervalMinutes` (default 5).

## ⚠️ Security note (spotted while wiring config, unrelated to this feature)

The live BUSY password currently in use is very weak (`12345`), and — per the earlier networking
work — **port 981 is presently open to any source IP** on the internet, in plaintext. That's a real
risk for a production accounting system. Recommend: **change the password to something strong**,
and prioritise the earlier-flagged follow-up of restricting port 981 to the connector's IP (and/or
TLS) once the VPS is in place. Not urgent enough to block today's work, but shouldn't sit for long.
