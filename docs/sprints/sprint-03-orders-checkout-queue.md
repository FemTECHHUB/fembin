# Sprint 3 — Orders & Checkout Queue

**Goal:** sales reps can create orders; cashiers can find them by phone lookup or the live
queue. No payment or BUSY posting yet — this sprint is the order lifecycle up to "ready to pay."

**Depends on:** Sprint 0 (does not need Sprint 1/2 — this workstream is independent of catalog sync)
**PRD references:** §6, `docs/reference/11-solution-overview.md` (Checkout Queue / phone-lookup UX design)

## Scope

- [ ] Postgres schema: `orders`, `order_items` (PRD §6 data model)
- [ ] `POST /api/v1/orders` — create order (items, branch, customer phone/name)
- [ ] `GET /api/v1/orders?branch=&status=` — the Checkout Queue
- [ ] `GET /api/v1/orders/lookup?phone=` — **this is the primary cashier handoff mechanism**,
      not a QR code (deliberate decision — customers here are not tech-inclined, see
      `docs/reference/11-solution-overview.md` §5)
- [ ] `GET /api/v1/orders/{code}`, `DELETE /api/v1/orders/{code}` (cancel while still pending/unpaid)
- [ ] The `outbox` table (schema only this sprint — the worker that drains it is Sprint 4)

## Out of scope

- Payment of any kind (Sprint 4).
- Posting anything to BUSY (Sprint 4) — orders in this sprint exist **only** in our own database.

## Definition of Done

- [ ] An order created by one "rep" session is immediately visible in another "cashier" session's
      queue and via phone lookup — verify with an integration test simulating both roles.
- [ ] Cancelling a pending order works; a paid order cannot be cancelled through this endpoint
      (guard now, even though "paid" doesn't exist until Sprint 4 — write the check so Sprint 4
      doesn't have to retrofit it).
- [ ] Order code generation is collision-safe under concurrent creation (test with parallel
      requests, not just sequential).
