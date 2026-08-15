# Sprint 0 — Foundations & Scaffolding

**Goal:** a clean, properly-structured Python project that can talk to BUSY and pass its own
tests — nothing product-facing yet, but the foundation everything else builds on.

**Depends on:** nothing (first sprint)
**PRD references:** §9 (Migration Plan)

## Scope

- [ ] Repo structure per `CLAUDE.md` §"Project Structure" (`src/` layout, `tests/`, `alembic/` migrations, etc.)
- [ ] `pyproject.toml` — dependencies (FastAPI, httpx, SQLAlchemy, Alembic, pydantic, pytest), linting (ruff), formatting (black), type checking (mypy)
- [ ] Config/secrets management — `.env` pattern, `pydantic-settings`, **no secrets ever committed**
- [ ] Postgres running (local dev via docker-compose is fine) + Alembic migration scaffolding
- [ ] Port `busyClient.js` → `app/busy/client.py` — same header-based call pattern, same service codes (see `docs/reference/02-service-codes.md`)
- [ ] Port `xmlUtil.js` → `app/busy/xml_util.py` — **both** parsers (`parse_rowset_xml`, `parse_element_xml`), **including the numeric-entity-decoding fix** (`&#x27;` etc. — a real bug found in the Node prototype, see `docs/reference/14-command-center.md`)
- [ ] A mock BUSY server for tests (`tests/fixtures/mock_busy.py`) — port the logic from the Node prototype's `mock-busy.js`, extended to also mock a couple of real captured responses (use the real XML samples in `docs/reference/12-schema-findings.md` as fixtures, not invented ones)
- [ ] CI: lint + type-check + test on every push, before anything else is built on top
- [ ] Logging setup — structured logs, request IDs, no `print()`

## Out of scope

- Any BUSY *write* calls (`SC=2`/`5`/`6`/`7`) — read-only this sprint, same caution as the whole engagement so far.
- Any product-facing API endpoint.

## Definition of Done

- [ ] `pytest` passes, including a test that runs `parse_rowset_xml` and `parse_element_xml`
      against the **real captured XML fixtures** copied from the Node prototype's `output/`
      folder (not synthetic data) — this is how the prototype caught 2 real bugs; don't lose
      that discipline.
- [ ] `busy_client.py` successfully runs a live `SC=1` query against the test BUSY company
      (manually verified once, not part of CI — CI uses the mock).
- [ ] `ruff` / `mypy` clean, no `# type: ignore` without a comment explaining why.
- [ ] README explains how to run the project locally in under 5 commands.
