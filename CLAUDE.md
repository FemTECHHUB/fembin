# CLAUDE.md — Engineering Rules for the BUSY Integration Platform

This file governs how AI agents (and anyone else) work in this repository. It is not
aspirational — every rule here exists because of something specific we already learned the
hard way during the research phase (`Busin/docs/` — the prototype/archive folder). Read
`docs/PRD.md` for *what* we're building and `docs/sprints/` for *when*; this file is *how*.

**If a sprint task and this file conflict, this file wins.** Flag the conflict in the sprint
doc rather than silently picking one.

---

## 1. What this project is

A Python backend that connects **BUSY** (accounting software, integrated over its "as Web
Service" HTTP API) to: a public e-commerce website, an internal sales-order/cashier app across
multiple branches, a dynamic loyalty scheme, and credit-partner reconciliation. Full detail in
`docs/PRD.md`.

A working **Node.js prototype exists at `../Busin/code/busy-probe/`.** It is not legacy code to
ignore — it's the validated proof that the approach works, including two real bugs it found and
fixed. Every "port X from the prototype" instruction in the sprint docs means: **read that code
first, understand why it's shaped the way it is, then write the Python equivalent** — not
"write something similar from memory."

---

## 2. Non-negotiable architecture rules

### 2.1 Modularity — strict layering, one direction of dependency

```
API layer (FastAPI routes)
   ↓ depends on
Domain/service layer (orders, loyalty, sync, reconciliation — pure business logic)
   ↓ depends on
Integration layer (busy/, integrations/woocommerce.py, integrations/moniepoint.py)
   ↓ depends on
Infrastructure (db/, outbox worker, config)
```

- **Domain logic never imports the API layer.** A service function must be callable from a
  test, a CLI script, or a route handler identically.
- **Domain logic never talks to BUSY/WooCommerce/Moniepoint directly** — it calls an interface
  in the integration layer. This is what lets BUSY calls be mocked in tests and (in principle)
  lets any one integration be replaced without touching business logic.
- **No feature reaches directly into another feature's tables.** Loyalty reads order data
  through a defined interface (a function/service call), not a raw join into `orders` from
  `loyalty/`. This is what "easy to build upon" concretely means — a new feature added later
  shouldn't need to understand every other feature's internals.

### 2.2 Every BUSY write goes through the outbox queue — no exceptions

This was the single most repeated lesson of the research phase: BUSY is one instance, processes
requests seriously (verified: 17s+ for a full sync of a *small* company), and a request handler
that calls BUSY synchronously will not hold up under concurrent load (see PRD §8 NFR1, §11).

- Every `SC=2` (add voucher/master) call is enqueued as an `outbox` row, never called inline
  from a request handler.
- A single background worker (or a small, deliberately-bounded pool — do not casually add
  concurrency here without re-reading PRD §11's open question about BUSY's real concurrent-write
  behavior, which is **still unmeasured**) drains it.
- Every job carries an **idempotency key** (order code, or the same value used as Moniepoint's
  `merchantReference`). Before posting, check whether this key already produced a result. A
  retried request must never double-post. This is not optional hardening — it's a correctness
  requirement for a system that touches real accounting data.

### 2.3 Incremental sync is the default, not an optimization

Every BUSY read that pulls a list defaults to `WHERE Stamp > last_seen_checkpoint`, checkpoint
persisted in `sync_state`, advanced **only after a successful write to our own database** (a
failed fetch must never advance the checkpoint — verified behavior in the prototype, don't
regress it). `full=true` exists as an explicit escape hatch, not the default.

### 2.4 Mark inactive, don't delete

A BUSY record going blocked/deactivated is reflected as `is_active = false` in our mirror, never
a `DELETE`. (A real bug in the prototype: filtering inactive records out *before* storage meant
a newly-blocked record silently never updated once incremental sync replaced full re-pulls.)

### 2.5 Receipts come from BUSY, never fabricated

Once a voucher is posted, its receipt is read back from BUSY (`SC=8`) and that data — including
BUSY's own assigned invoice number — is what gets shown/printed. Never construct a receipt from
the order's local data alone.

---

## 3. Project structure

```
fembin/
├── CLAUDE.md                 ← this file
├── docs/
│   ├── PRD.md
│   ├── sprints/               ← sprint plan, one file per sprint
│   └── reference/              ← copied research findings (BUSY schema, constants, examples)
├── app/
│   ├── main.py                 ← FastAPI app factory
│   ├── config.py                ← pydantic-settings, env-driven, no hardcoded secrets
│   ├── busy/
│   │   ├── client.py             ← ported busyClient.js
│   │   ├── xml_util.py           ← ported xmlUtil.js (both parsers + entity-decoding fix)
│   │   └── constants.py           ← MasterType/VchType enums (docs/reference/03-constants.md) — never magic numbers inline
│   ├── integrations/
│   │   ├── woocommerce.py
│   │   └── moniepoint.py
│   ├── domain/
│   │   ├── catalog/              ← Sprint 1-2
│   │   ├── orders/                ← Sprint 3-4
│   │   ├── loyalty/                ← Sprint 6-7
│   │   └── credit_partners/         ← Sprint 8
│   ├── outbox/
│   │   ├── models.py
│   │   └── worker.py
│   ├── api/
│   │   └── v1/                    ← route modules, thin — validation + call domain layer, nothing else
│   └── db/
│       ├── models.py
│       └── session.py
├── alembic/                     ← migrations — every schema change is a migration, never a manual `ALTER`
└── tests/
    ├── fixtures/
    │   ├── mock_busy.py           ← ported mock-busy.js
    │   └── real_xml_samples/       ← actual captured BUSY responses, copied from the prototype — use real data in tests, not invented shapes
    └── ...                        ← mirrors app/ structure
```

Route handlers under `api/` should be short — parse/validate input, call one domain function,
return its result. If a route handler has business logic in it, that logic belongs in `domain/`.

---

## 4. Coding standards

- **Type hints everywhere.** Function signatures, not just complex ones. `mypy` runs in CI and
  must pass.
- **Formatting:** `black`, no debate, no manual style choices.
- **Linting:** `ruff`, CI-enforced.
- **No magic numbers for BUSY constants.** `VchType.SALE` (an enum from `busy/constants.py`),
  never a bare `9` in application code — the constants doc (`docs/reference/03-constants.md`) is
  the source of truth, and enums make the code self-documenting and catch typos at review time.
- **Docstrings on every public function** in `domain/` and `busy/` — one sentence of *why*, not
  a restatement of the function name.
- **No dead code.** No commented-out blocks "in case we need it later" — that's what version
  history is for. No unused imports, no unreachable branches.
- **No silent `except:` blocks.** Catch specific exceptions; log what happened; never swallow an
  error that should have surfaced.

---

## 5. Testing

- **Every domain function gets a unit test.** Every BUSY-facing function gets an integration
  test against the mock BUSY server (`tests/fixtures/mock_busy.py`), and — where the sprint doc
  says so — a manually-verified real call against the live test company.
- **Use real captured data as test fixtures, not invented XML.** The prototype's two real bugs
  (`BlockedMaster` being the text `'True'`, not `'1'`; XML numeric entities like `&#x27;` not
  being decoded) were both found because real data was used in testing. Synthetic "looks about
  right" fixtures would not have caught either.
- **A sprint's Definition of Done is the contract.** Don't mark a sprint file's checklist done
  from memory — actually run the test/check it describes.

---

## 6. Security

- **No secrets in code, ever** — env vars via `config.py`, `.env` in `.gitignore`.
- **The BUSY service account is dedicated**, not a human's login (NFR5) — set this up in Sprint 5,
  don't defer it.
- **Port 981 is restricted to the backend's IP** — the research phase left it open to any
  source with a weak password; Sprint 5 must close this, and closing it must be *verified*
  (an external port scan), not just configured and assumed.
- **Every external-facing endpoint validates its input** (pydantic models handle most of this —
  don't bypass it with raw dict access).
- **Audit trail:** the actual cashier/rep's identity is stamped into BUSY voucher narrations
  (NFR6) — BUSY's own `CreatedBy` will otherwise only ever show the shared service account.

---

## 7. Git & review workflow

- Feature branches off `main`, named `sprint-N-short-description`.
- No direct commits to `main`.
- A PR is reviewable if: tests pass, lint/type-check pass, the relevant sprint file's Definition
  of Done items are checked off in the PR description, and any new BUSY behavior discovered is
  reflected back into `docs/reference/` or `docs/PRD.md` — don't let undocumented tribal
  knowledge accumulate.
- Commit messages: what changed and why, not just what.

---

## 8. BUSY gotchas — read this before touching `busy/` or any sync code

Condensed from the research phase so nothing here gets silently re-discovered:

| Gotcha | Detail |
|---|---|
| Bit columns are text | `BlockedMaster`/`DeactiveMaster`/`VchCancelled` come back as the strings `'True'`/`'False'`, not `1`/`0`. Check both `'True'` and `'1'` defensively. |
| XML entities | Numeric character refs (`&#x27;`, `&#39;`) appear in real data (customer names) and are NOT covered by decoding only the 5 named XML entities. Decode both. |
| `VchNo` is padded | Comes back with leading whitespace in some queries — always `.strip()`. |
| Stock isn't on the Item master | `GetMasterXML` for an Item has no stock/quantity field at all. Stock must be derived from transactions — mechanism now decoded (next row), but the resulting number is still **unverified against BUSY's own GUI**. Do not invent a stock number, and do not wire a derived one into the catalog sync yet. |
| `Tran2` stock-derivation mechanism — **decoded 2026-08-15, unverified against a ground truth** | Confirmed live against two real stock-tracked items (Cable-infinix Micro/Typ C, codes 1613/1614): `RecType=2` rows are item-quantity-movement lines (`MasterCode1`=Item, `MasterCode2`=Material Center, `Value1`=signed Qty). `RecType=1` = ledger/account entries, not movements — exclude. `RecType=20` = a Sale/Purchase **Quotation** item line — quotations don't move stock, exclude (a second, explicit `VchType` filter backs this up — see `app/domain/catalog/stock.py`'s `STOCK_MOVING_VCH_TYPES`). `ItemBal1-3`/`Balance1-3` were `0` on every real row seen, including genuine Stock Journal movements — BUSY isn't maintaining a usable running balance for this company; sum raw movements instead. Physical Stock (`VchType=61`) is assumed to reset the running total rather than add to it (standard software convention) but this is **inferred, not confirmed** — the one real example had a delta of 0, consistent with either reading. **No GUI cross-check has been done** — the computed totals for 1613/1614 (-11 and +11, an exact-opposite pair from what looks like a single test transfer) have never been compared against BUSY's own displayed stock figure. Get that comparison before trusting this. |
| `Stamp` granularity is uncertain | Values observed were small (1–4) even across thousands of records — possibly a coarser batch counter, not strict per-row versioning. Works correctly in every test so far, but verify with a single-record-edit-and-recheck test before leaning on it harder at scale. |
| BUSY session drops | The company-open session on the BUSY desktop app has dropped repeatedly and unpredictably during research (not a code bug). Sprint 5's runbook exists because of this — expect it, monitor for it, don't assume a `Please open a company` error means our code is wrong. |
| One BUSY instance, no proven write concurrency | Never assume BUSY handles concurrent writes gracefully — we have no data on this. This is *why* the outbox queue exists. |
| Real confirmed Item field names | `Name`, `SalePrice`, `MainUnit`, `ParentGroup`, `DoNotMaintainStkBal` — confirmed against live data. Do not use `Price`/`Unit`/`ItemGroup` (earlier, wrong guesses). |
| Sale Quotation XML shape — **confirmed 2026-08-15** | Root tag `<SaleQuotation>` guess was correct (verified via `GetVchXML` on real existing quotations, then a live test post — Busin's `code/busy-probe/src/quotationTest.js`). Required fields beyond the guessed shape: `STPTName` (Sale Type) must be a real one for this company (`Repair` confirmed valid — the generic doc example's `Local-ItemWise` does NOT exist here). `app/domain/orders/quotations.py` needs `STPTName` added if it isn't already there. |
| `VchNo` must be pre-computed, not arbitrary | This company has **Detailed Audit Trail enabled** — posting a `VchNo` BUSY doesn't recognize as the next-in-sequence for that series returns `"Voucher number can not be blank"` (misleading — it's a format/sequence rejection, not literally blank). BUSY numbers each voucher **series** independently with its own prefix (e.g. series `Main` → prefix `RCC-`, series `RC Taiwo` → prefix `JCT-`, discovered — not documented anywhere). Before every write: query `SELECT VchNo FROM Tran1 WHERE VchType=<n> AND LTRIM(VchNo) LIKE '<prefix>-%'`, take the max numeric suffix, use `+1`. Applies to Sale (9) too, not just Quotation — same audit-trail flag. |
| `VchNo` SQL comparisons need `LTRIM` | Confirmed again with a live test: `WHERE VchNo='RCC-2'` returns 0 rows for a voucher that exists (`VchCode` lookup proves it) because the column is stored left-padded/fixed-width. Always `WHERE LTRIM(VchNo)='...'`, not just `.strip()` on the way *out* — the earlier gotcha row only covered the read side. |
| BUSY write latency — **measured 2026-08-15**, was the PRD's top open risk | Live `SC=2` (Add Voucher) on a Sale Quotation: **~700–760ms** write, ~450–680ms for an immediate `SC=8`/`SC=1` read-back, ~1.2–1.3s round trip write→confirmed-readable. Data was visible in `Tran1` immediately (no replication lag) once the `LTRIM` query bug above was fixed. Measured against Sale Quotation only (no stock/accounting posting) — a real Sale (VchType=9) may differ since it also posts ledger/stock updates; re-measure before treating this as representative for Sprint 4. |
| No barcode data in BUSY — **checked live 2026-08-20** | Queried `Master1 WHERE MasterType=6` (Item) for `Name`, `PrintName`, `Alias`, `HSNCode` on all 8 real items: `PrintName` merely mirrors `Name`; `Alias`/`HSNCode` are empty on every row. There is no barcode field populated anywhere for this company's items — barcode scanning cannot "match BUSY," it has to be a field we own and maintain ourselves (`Product.barcode` in `app/db/models.py`, local-only, excluded from catalog sync's upsert). |
| Sales people/salesmen ARE a real BUSY master — don't build a local one | `MasterType=33` is "Executive" in BUSY's own schema, "Salesmen" in its UI — confirmed real in the research phase (`docs/reference/14-command-center.md`), synced with the exact same bulk-SQL pattern as Material Center (`app/domain/catalog/sync.py`'s `sync_salesmen`). **First got this wrong 2026-08-20**: built a table we owned and let callers create rows into (`sales_people`) before realizing BUSY already has the real master — corrected same day (`Salesman` model, read-only sync, dropped the local CRUD/reassign endpoints). Whether BUSY ties an Executive to a specific Material Center is **unconfirmed** — the generic `Master1` schema shows no such field, so no branch-scoping is applied to the synced list. The original research-phase probe against this same company found the Executive master **genuinely empty** (business wasn't using the feature) — don't be surprised if a live sync returns zero rows; that's expected until someone enters salesmen in BUSY itself. |
| Real BUSY connection timeouts can have an empty exception message | A live `SC=2` call that hung past the client's 30s timeout (BUSY session flakiness, same row above) raised an `httpx` timeout whose `str()` is `""` — `app/outbox/worker.py`'s old `job.last_error = str(exc)` silently recorded nothing. Fixed 2026-08-20 to fall back to the exception's class name when the message is empty; if you write other exception-to-string logging against BUSY calls, don't assume `str(exc)` is never blank. |

---

## 9. How an AI agent should operate in this repo

1. Read `docs/PRD.md` (relevant section), this file, and the specific sprint doc — in that order
   — before writing code.
2. If a sprint doc's scope conflicts with something learned since it was written, say so and
   propose the update — don't silently deviate or silently comply with a now-wrong instruction.
3. Prefer extending an existing module over adding a new pattern. If two features need similar
   logic, look for how the existing feature did it before inventing a second way.
4. Never mark a Definition of Done item complete without having actually verified it.
5. When something about BUSY's real behavior is discovered that isn't in §8 above, add it there
   — this table is the whole point of not repeating the research phase's cost.
