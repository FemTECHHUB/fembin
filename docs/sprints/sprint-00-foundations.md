# Sprint 0 — Foundations & Scaffolding

**Goal:** a clean, properly-structured Python project that can talk to BUSY and pass its own
tests — nothing product-facing yet, but the foundation everything else builds on.

**Depends on:** nothing (first sprint)
**PRD references:** §9 (Migration Plan)

## Scope

- [x] Repo structure per `CLAUDE.md` §"Project Structure" (`src/` layout, `tests/`, `alembic/` migrations, etc.)
- [x] `pyproject.toml` — dependencies (FastAPI, httpx, SQLAlchemy, Alembic, pydantic, pytest), linting (ruff), formatting (black), type checking (mypy)
- [x] Config/secrets management — `.env` pattern, `pydantic-settings`, **no secrets ever committed**
- [x] MySQL running (local dev via docker-compose is fine) + Alembic migration scaffolding
- [x] Port `busyClient.js` → `app/busy/client.py` — same header-based call pattern, same service codes (see `docs/reference/02-service-codes.md`)
- [x] Port `xmlUtil.js` → `app/busy/xml_util.py` — **both** parsers (`parse_rowset_xml`, `parse_element_xml`), **including the numeric-entity-decoding fix** (`&#x27;` etc. — a real bug found in the Node prototype, see `docs/reference/14-command-center.md`)
- [x] A mock BUSY server for tests (`tests/fixtures/mock_busy.py`) — port the logic from the Node prototype's `mock-busy.js`, extended to also mock a couple of real captured responses (use the real XML samples in `docs/reference/12-schema-findings.md` as fixtures, not invented ones)
- [x] CI: lint + type-check + test on every push, before anything else is built on top
- [x] Logging setup — structured logs, request IDs, no `print()`

## Out of scope

- Any BUSY *write* calls (`SC=2`/`5`/`6`/`7`) — read-only this sprint, same caution as the whole engagement so far.
- Any product-facing API endpoint.

## Definition of Done

- [x] `pytest` passes, including a test that runs `parse_rowset_xml` and `parse_element_xml`
      against the **real captured XML fixtures** copied from the Node prototype's `output/`
      folder (not synthetic data) — this is how the prototype caught 2 real bugs; don't lose
      that discipline. (See `tests/fixtures/real_xml_samples/README.md` for exactly which
      fixtures are raw copies vs. reconstructed from real captured field values — the two
      documented bug scenarios, BlockedMaster='True' and the `&#x27;ENAIBE...` numeric entity,
      weren't preserved as raw XML in the prototype's `output/` folder, only described in
      `docs/reference/14-command-center.md`, so those two specific fixtures are reconstructed
      from that write-up rather than copied byte-for-byte.)
- [x] `busy_client.py` successfully runs a live `SC=1` query against the test BUSY company
      (manually verified once, not part of CI — CI uses the mock). **Done 2026-08-15** — port
      981 became reachable from this environment (it wasn't earlier in this sprint; see the
      history above, left intentionally rather than deleted). Live query via
      `BusyClient.run_query`: `SELECT TOP 3 Code, Name FROM Master1 WHERE MasterType = 11`
      returned real data — `[{'Code': '201', 'Name': 'Main Store'}, {'Code': '1155', 'Name':
      'Repair Centre Taiwo'}]` — confirming the client, the pagination-style `SELECT TOP N`
      query shape, and `parse_rowset_xml` all work end-to-end against real BUSY, not just the
      mock.
- [x] `ruff` / `mypy` clean, no `# type: ignore` without a comment explaining why.
- [x] README explains how to run the project locally in under 5 commands.
