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
| Stock isn't on the Item master | `GetMasterXML` for an Item has no stock/quantity field at all. Stock must be derived from transactions — unsolved, tracked in PRD §5. Do not invent a stock number. |
| `Stamp` granularity is uncertain | Values observed were small (1–4) even across thousands of records — possibly a coarser batch counter, not strict per-row versioning. Works correctly in every test so far, but verify with a single-record-edit-and-recheck test before leaning on it harder at scale. |
| BUSY session drops | The company-open session on the BUSY desktop app has dropped repeatedly and unpredictably during research (not a code bug). Sprint 5's runbook exists because of this — expect it, monitor for it, don't assume a `Please open a company` error means our code is wrong. |
| One BUSY instance, no proven write concurrency | Never assume BUSY handles concurrent writes gracefully — we have no data on this. This is *why* the outbox queue exists. |
| Real confirmed Item field names | `Name`, `SalePrice`, `MainUnit`, `ParentGroup`, `DoNotMaintainStkBal` — confirmed against live data. Do not use `Price`/`Unit`/`ItemGroup` (earlier, wrong guesses). |

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
