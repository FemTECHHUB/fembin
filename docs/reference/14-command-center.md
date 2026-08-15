# 14 — Command Center: dummy frontend + SQLite store

`code/busy-probe/` now has a small local web app to fetch from BUSY on demand and browse
what's stored, backed by a real SQL database.

## Run it

```bash
cd code/busy-probe
node src/webApp.js          # http://localhost:3000
```

Open that URL in a browser. Buttons fetch fresh data from BUSY into `catalog.db` (SQLite):
**Material Centers, Customers, Products, Salesmen, Sale Types, Sales**, plus a
**Fetch Everything** button. Six tabs browse what's stored, with a search box that filters
the active tab. On the **Sales** tab, each row has a **"View receipt"** link that fetches the
full voucher XML on demand and shows it in a modal.

## What's under the hood

| Piece | File |
|---|---|
| SQLite schema + connection | `src/db.js` (`items`, `customers`, `material_centers` tables) |
| Shared fetch/store logic | `src/catalogSync.js` — used by both the CLI and the web buttons |
| CLI loader | `src/loadToDb.js` (`npm run load-db`) |
| Web server + API | `src/webApp.js` |
| Frontend page | `public/index.html` (vanilla JS, no framework) |

- **Products** — bulk SQL lists active Item codes, then one `GetMasterXML` (SC=9) call per
  item for the real fields (confirmed mapping, see `12-schema-findings.md`).
- **Customers** — Accounts (MasterType 2), **bulk SQL only**, no per-record calls — there can
  be thousands (this company has 3,376), so a single query keeps it fast and light on BUSY.
- **Material Centers** — bulk SQL, same pattern as customers.
- **Salesmen** (Executive, MasterType 33) & **Sale Types** (MasterType 13) — same simple
  bulk-SQL pattern, via a shared `fetchAndStoreSimpleMaster()` helper.
- **Sales** (Tran1, VchType 9) — bulk SQL with the customer and branch names resolved via
  **SQL JOIN** back to `Master1` (not per-row lookups) — all 4,226 sales in ~3 seconds.
- **Receipts** — deliberately **not** bulk-fetched. One `GetVchXML` (SC=8) call per voucher,
  **on demand**, triggered by clicking "View receipt" on a specific sale. Pulling full receipt
  detail for thousands of vouchers up front would hammer BUSY for data nobody's looking at yet.

## Two real bugs found and fixed while wiring this up against live data

1. **`BlockedMaster`/`DeactiveMaster` are the text `'True'`/`'False'`, not `'1'`/`'0'`.**
   The original filter checked for `'1'` — it happened not to bite because nothing in the
   test data was blocked, but it was wrong. Fixed in `catalogSync.isActive()`, reused
   everywhere now (`fetchCatalog.js`, `syncService.js`, `loadToDb.js` all share it).
2. **XML numeric character entities weren't decoded.** A real customer name came through as
   `&#x27;ENAIBE L C (MRS)` instead of `'ENAIBE L C (MRS)` — `decodeXmlEntities` only handled
   the 5 named entities (`&amp;` etc.), not `&#x27;`/`&#39;`-style numeric refs. Fixed in
   `xmlUtil.js`.

## Confirmed against this company's real data

- 8 active Items (a repair shop's item list: cable accessories + tiered "Diagnosis Fee"
  service items — `DoNotMaintainStkBal` correctly distinguishes services from physical goods).
- 2 active Material Centers ("Main Store", "Repair Centre Taiwo").
- 3,376 active Customers (Accounts) — count changed **while testing**, confirming this is
  live production data, not a snapshot.

## Confirmed on the transaction side too

- **4,226 Sale vouchers** exist — pulled as a list (header + resolved names) in ~3 seconds.
- **Salesmen (Executive master) is genuinely empty** — this business doesn't use that BUSY
  feature. Shown honestly in the UI rather than assumed broken.
- A real receipt (`VchCode 9701`) confirmed the full voucher shape: customer name + phone,
  item + repair notes, pricing, broker, and accounting entries — everything needed to render
  an actual receipt later.

## ⭐ Incremental sync (the background-worker foundation)

Every fetch is now **incremental by default**: BUSY's `Stamp` column is a changelog
counter, and we persist the highest `Stamp` seen per entity in a `sync_state` table.
Each fetch asks BUSY for `WHERE Stamp > lastSeenStamp` — only new/changed rows come
back. Proven against live data:

| Run | Time | Result |
|---|---|---|
| 1st run (checkpoints at 0) | 17.3s | Everything pulled (2 MCs, 3,377 customers, 8 products, 4,226 sales) |
| 2nd run, immediately after | **2.2s** | **0 changes everywhere** — correctly detected nothing changed |

A UI checkbox ("Full refresh") forces a complete re-pull when needed (first run,
suspected drift, schema change) — everything else defaults to incremental.

**Records that go blocked/deactivated are marked `is_active = 0`, not deleted.** An
incrementally-synced mirror that only ever inserts/updates would otherwise leave stale
rows around forever once something is blocked in BUSY — the UI shows an active/inactive
badge instead.

**Caveat worth knowing:** the actual `Stamp` values that came back were small (1–4),
not proportional to record counts (e.g. 8 items → max stamp 2). That suggests `Stamp`
may be a coarser batch/generation counter rather than a strict per-row version. It
still worked correctly here (proven by the zero-change second run), but before relying
on it for the production connector, worth doing one more test: edit a single record in
BUSY, then confirm just that record's Stamp increases past the checkpoint.

## Voucher types — now generic, not just Sales

The old "Sales" tab is now a **Vouchers** tab with a **type dropdown** covering all 28
voucher types from `03-constants.md` (Sale, Purchase, Receipt, Payment, Journal, Credit
Note, ...). Same generic `fetchAndStoreVouchers()` function handles any type — proven by
switching to **Receipt (VchType 14)** and pulling 2,151 real receipts in 2.7s with zero
code changes. Pick a type, hit "Update this type."

## Known limitation (unchanged from `13-sync-service.md`)

Stock is still not pulled — it isn't on the Item master; needs deriving from transactions
(see `12-schema-findings.md` §4). Not attempted yet.
