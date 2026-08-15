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
(uses the mock BUSY server — no live BUSY connection needed):

```bash
docker compose up -d                  # local MySQL on localhost:3307
uv sync                               # install dependencies
uv run pytest                         # run the test suite
```

To also run the app against a real database and/or real BUSY:

```bash
cp .env.example .env                  # fill in BUSY_USERNAME/BUSY_PASSWORD for live BUSY calls
uv run alembic upgrade head           # apply migrations
uv run uvicorn app.main:app --reload  # currently exposes only /health — no product-facing
                                       # endpoints yet, see docs/sprints/sprint-00-foundations.md
```

Run lint / format / type-check: `uv run ruff check .`, `uv run black --check .`, `uv run mypy app`.

Run the standalone mock BUSY server (for manually exercising `app/busy/client.py` without a real
BUSY connection): `uv run python -m tests.fixtures.mock_busy` — listens on `127.0.0.1:8981`.

## Status

Sprint 0 (Foundations & Scaffolding) complete — see
[`docs/sprints/sprint-00-foundations.md`](docs/sprints/sprint-00-foundations.md) for its
Definition of Done. Next: Sprint 1, BUSY Read Layer + Incremental Sync (Catalog).
