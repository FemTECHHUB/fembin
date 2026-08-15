# Sprint 4 — Payments & BUSY Posting

**Goal:** the core, highest-stakes loop of the whole platform — cashier takes payment, and only
*after* payment is confirmed does a real Sale + Receipt post to BUSY, with a real BUSY invoice
number, through the durable queue. This is the sprint where correctness matters most.

**Depends on:** Sprint 3 (orders) and Sprint 0 (BUSY client)
**PRD references:** §6, §8 (NFRs — read every one before starting), `docs/reference/10-pos-integration-proposal.md` (Moniepoint API detail)

## Scope

- [ ] `payments` table (PRD §6 data model)
- [ ] `POST /api/v1/orders/{code}/payment/cash`
- [ ] `POST /api/v1/orders/{code}/payment/terminal` — pushes to Moniepoint/Opay
      (`terminalSerial`, `amount`, **`merchantReference` = the order code** — this IS the
      idempotency key, confirmed API shape in `docs/reference/10-pos-integration-proposal.md`)
- [ ] `GET /api/v1/orders/{code}/payment/status` (polling) **and** `POST /api/v1/webhooks/moniepoint` (push) — support both, prefer webhook, fall back to poll
- [ ] The **outbox worker**: drains `outbox` jobs one at a time, posts Sale (`SC=2`) then Receipt
      (`SC=2`) to BUSY, retries on transient failure, marks `failed` (not silently dropped) after
      a max-attempts threshold
- [ ] **Idempotency is mandatory, not a nice-to-have (NFR2):** before posting, check whether this
      order's job already produced a BUSY voucher code; never post twice for the same order code
- [ ] `GET /api/v1/orders/{code}/receipt` — returns data **read back from BUSY** after posting
      (`SC=8`), never fabricated from the order's local data (NFR8 — "receipt from BUSY" is a
      hard requirement, not a preference)
- [ ] Stamp the actual cashier's identity into the voucher narration (NFR6) — BUSY's own
      `CreatedBy` will otherwise show only the shared service account for every sale

## Out of scope

- Loyalty point earning (Sprint 6 hooks into this sprint's posting event later — don't build it
  now, but don't make the posting code hard to extend either, per `CLAUDE.md`'s modularity rule).
- Credit-partner sales (Sprint 8).

## Definition of Done

- [ ] **A real voucher posted to the test BUSY company, with its real invoice number retrieved
      and printed/returned** — this sprint is not done until this has actually happened once,
      not just mocked.
- [ ] Duplicate-submission test: fire the same "finalize" request twice (simulating a network
      retry) — confirm exactly one BUSY voucher results, not two.
- [ ] A simulated BUSY outage mid-post: confirm the job lands in `failed`/retry state, is visible
      via an admin endpoint, and recovers cleanly once BUSY is reachable again — no manual DB
      surgery required.
- [ ] Payment-before-sale invariant tested: no code path can create a Sale voucher without a
      `payments` row in `confirmed` status for that order.
