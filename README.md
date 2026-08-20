# fembin — BUSY Integration Platform

This is the **production working directory** for the BUSY ↔ website ↔ app ↔ loyalty platform.
The earlier research/prototype phase lives in `../Busin/` (kept as an archive — the Node.js
prototype there proved the approach against live BUSY data and is not being thrown away).

## Start here

1. **[`CLAUDE.md`](CLAUDE.md)** — engineering rules. Read this before writing any code, not after.
2. **[`docs/PRD.md`](docs/PRD.md)** — what we're building and why.
3. **[`docs/sprints/`](docs/sprints/README.md)** — when, broken into 10 bounded sprints.
4. **[`docs/reference/`](docs/reference/)** — curated copies of the validated technical findings
   (real BUSY schema, service codes, constants, POS integration details) the PRD and sprints
   depend on.

## Running locally

Requires [`uv`](https://docs.astral.sh/uv/) and Docker. To install and run the test suite
(BUSY is mocked; the catalog sync tests do hit a real local MySQL — see
`docs/sprints/sprint-01-busy-read-layer.md`):

```bash
docker compose up -d                  # local MySQL on localhost:3307
uv sync                               # install dependencies
uv run alembic upgrade head           # apply migrations
uv run pytest                         # run the test suite
```

To also run the app itself (and/or against real BUSY):

```bash
cp .env.example .env                  # fill in BUSY_USERNAME/BUSY_PASSWORD for live BUSY calls
uv run uvicorn app.main:app --reload  # serves /health, the catalog read API, and the
                                       # outbox/quotations endpoints under /api/v1
```

Every real BUSY write goes through the outbox queue (`app/outbox/`), never inline from a
request handler (CLAUDE.md §2.2). `POST /api/v1/quotations` enqueues a Sale Quotation
(shape confirmed live 2026-08-15, see CLAUDE.md §8); `GET /api/v1/quotations` lists all of
them with status (queued/running/done/failed) and the BUSY-assigned VchNo/VchCode once
posted; `GET /api/v1/outbox/{id}` looks up any single enqueued job. The outbox worker and
the catalog sync scheduler are both off by default per-process — set
`OUTBOX_WORKER_ENABLED=true` / `CATALOG_SYNC_ENABLED=true` to run them.

### Auth

Every user is tied to exactly one `MaterialCenter` (branch) — CLAUDE.md NFR6: actions need
a real identity, not just the shared BUSY service account. `POST /api/v1/auth/login`
returns a JWT (`JWT_SECRET_KEY` — set a real one outside dev, see `.env.example`).

The Sale Quotation routes require this token: `material_center_name` is no longer a
request field — it's always the caller's own assigned branch, and `GET /api/v1/quotations`
only ever shows that branch's quotations.

`POST /api/v1/auth/users` requires an authenticated **superadmin** (`User.is_superadmin`).
Since that's a chicken-and-egg problem for the very first one, bootstrap it by hand:

```bash
uv run python scripts/create_superadmin.py \
  --username admin --password '...' --full-name "Admin" --material-center-code 201
```

```bash
curl -s -X POST localhost:8000/api/v1/auth/login -H 'content-type: application/json' -d \
  '{"username":"taiwo.rep","password":"..."}'
# -> {"access_token": "...", "token_type": "bearer"}
curl -s localhost:8000/api/v1/quotations -H 'Authorization: Bearer <token>'
```

### Sales people and barcodes

Every Sale Quotation also names a sales person (`sales_person_id`) — distinct from the
logged-in `User`, since several people can share one till/login. This is BUSY's own
**Executive** master (`MasterType=33`, BUSY calls it "Salesmen" in its UI) — synced
read-only exactly like Product/Material Center (`app/domain/catalog/sync.py`'s
`sync_salesmen`, `app/db/models.py`'s `Salesman`), **not** something this app creates —
add/edit salesmen in BUSY itself (Administration → Masters → Executive), then sync.
`GET /api/v1/sales-people` lists the active ones. Recorded in the outbox job's own
payload, not the BUSY XML — there's no confirmed Narration/Remarks field on
`SaleQuotation` to carry it (CLAUDE.md §8). Whether BUSY ties an Executive to a specific
material center is unconfirmed, so the list isn't branch-scoped.

Products can carry a `barcode` (`PUT /api/v1/products/{code}/barcode`, superadmin-only) —
local-only, unlike sales people. Checked live 2026-08-20: this company's real BUSY Item
master has **no** barcode data anywhere, so this genuinely can't come from BUSY — it's
ours to maintain (CLAUDE.md §8).

### Dev-only test pages

`/console` — a small dependency-free HTML page (`app/static/console.html`, served
same-origin so no CORS is needed) for manually testing login, picking a sales person,
scanning/picking products, and creating/watching Sale Quotations. Not a production UI.

`/admin` (`app/static/admin.html`) — the same idea, for a superadmin: every user, every
quotation regardless of branch, every synced sales person (including inactive ones), and
barcode assignment. Backed by `GET /api/v1/admin/users`, `/admin/quotations`,
`/admin/sales-people`.

Every HTTP request is access-logged (`app.access` logger: method, path, status, duration).
Every catalog sync / outbox drain is logged per step with timing. Two ops scripts log a
full listing directly rather than going through the API — useful for eyeballing state in
the structured logs:
```bash
uv run python scripts/list_products.py     # every product in the local MySQL mirror
uv run python scripts/list_quotations.py   # every Sale Quotation, with status
```

Run lint / format / type-check: `uv run ruff check .`, `uv run black --check .`, `uv run mypy app tests scripts`.

Run the standalone mock BUSY server (for manually exercising `app/busy/client.py` without a real
BUSY connection): `uv run python -m tests.fixtures.mock_busy` — listens on `127.0.0.1:8981`.

## Status

Sprints 0-2 complete (Foundations, BUSY Read Layer + Incremental Sync, Website/WooCommerce
Sync) — see the respective sprint docs in `docs/sprints/` for each Definition of Done. Next:
Sprint 3, Orders & Checkout Queue.
