# Sprint 6 — Loyalty Engine: Core (Data Model + Rules Engine)

**Goal:** points accrue automatically on a real sale, computed by **configurable rules**, not
hardcoded logic. "Dynamic" is the explicit requirement here — changing the points rate must be
a data change (an API call), never a code deploy.

**Depends on:** Sprint 4 (hooks into the posting event) and Sprint 1 (customer records)
**PRD references:** §7

## Scope

- [ ] Postgres schema: `loyalty_customers`, `loyalty_tiers`, `loyalty_rules`, `loyalty_transactions` (PRD §7)
- [ ] The **rules engine**: given a sale (branch, category, amount, date), find active
      `loyalty_rules` matching its scope, apply `formula_json`, compute points. This must be
      genuinely data-driven — no `if` statement encoding a specific points rate anywhere in the
      engine's code
- [ ] Hook the engine into the Sprint 4 outbox worker: after a Sale voucher successfully posts,
      enqueue a `loyalty_earn` job (same outbox pattern — don't invent a second job mechanism)
- [ ] Tier evaluation: crossing a `min_lifetime_points` threshold updates `loyalty_customers.tier_id`
- [ ] `GET /api/v1/loyalty/customers/{code}`, `/history`
- [ ] `GET /api/v1/loyalty/tiers`, `POST`/`PUT /api/v1/loyalty/tiers` — CRUD, admin-only
- [ ] `GET /api/v1/loyalty/rules`, `POST`/`PUT /api/v1/loyalty/rules` — CRUD, admin-only

## Out of scope

- Redemption (Sprint 7).
- Customer export endpoint (Sprint 7 — grouped with admin-facing loyalty features).

## Definition of Done

- [ ] A live test: define a rule ("1 point per ₦100"), post a real sale through the Sprint 4
      pipeline, confirm the correct points land in `loyalty_transactions` and the customer's
      balance, with **zero code changes** between defining the rule and it taking effect.
- [ ] A second test: change the rule's rate via the API (e.g. a "double points" promo with
      `active_from`/`active_to`), confirm it applies only within that window.
- [ ] A sale with no matching active rule does not error — it simply earns nothing, logged clearly.
