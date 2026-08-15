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
