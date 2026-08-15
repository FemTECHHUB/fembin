# Sprint 7 — Loyalty Engine: Redemption & Admin

**Goal:** a cashier can apply a customer's points as a discount at checkout, and the business
can see and export the full loyalty picture.

**Depends on:** Sprint 6
**PRD references:** §7

## Scope

- [ ] `POST /api/v1/loyalty/redeem` — validates balance, computes discount value via the
      matching redeem-type `loyalty_rules`, writes the `loyalty_transactions` row
- [ ] Wire the computed discount into the order total **before** it's posted to BUSY as a Sale —
      same pattern as the `Discount` Bill Sundry line seen in real Sale XML (`docs/reference/04-examples.md`)
- [ ] `GET /api/v1/loyalty/customers/export` — **the full customer + loyalty data export** (this
      was the original ask that started the loyalty workstream — don't lose sight of it under the
      rest of the feature)
- [ ] `GET /api/v1/loyalty/reports/summary` — points issued/redeemed, tier distribution, top customers
- [ ] Basic guardrails: can't redeem more points than the balance; a redemption on a
      since-cancelled order is reversed

## Out of scope

- Any UI — this sprint is API + logic only, matching the rest of this PRD's backend-first scope.

## Definition of Done

- [ ] End-to-end: customer has points → cashier redeems some at checkout → order total reduced
      correctly → BUSY Sale reflects the discount → `loyalty_transactions` shows the redemption.
- [ ] Export endpoint returns every enrolled customer's full profile + running balance; verified
      against a manually-computed expected total for a test dataset (don't just trust it looks right).
- [ ] Attempting to redeem more points than available is rejected with a clear error, not a
      negative balance.
