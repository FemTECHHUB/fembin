# Sprint 8 — Credit Partners & Reconciliation

**Goal:** sales made through a credit/BNPL partner post against **that partner's own BUSY
account**, and reconciling what a partner owes is a three-way match, not a spreadsheet exercise.

**Depends on:** Sprint 4 (posting pipeline) and Sprint 5 (pilot-tested reliability, since this
extends the same posting path with a different party)
**PRD references:** §12

## Scope

- [ ] MySQL schema: `credit_partners`, `credit_partner_bills` (PRD §12)
- [ ] `POST /api/v1/credit-partners` — creates the BUSY Account under a dedicated **"Credit
      Partners" Account Group**, with `BillByBillBalancing=True` (BUSY's own mechanism — do not
      build a parallel receivables system, use what BUSY already does for this)
- [ ] Order flow change: when a sale is via a credit partner, the Sale voucher's party
      (`MasterName1`) is the **partner's account**, not the end consumer — the end consumer's
      identity is still captured in the order's own data for warranty/loyalty (loyalty accrual
      in Sprint 6/7 must still work off the real end-customer, not the partner — check this
      explicitly, it's an easy thing to get backwards)
- [ ] `GET /api/v1/credit-partners`, `/{id}/bills`
- [ ] `POST /api/v1/credit-partners/{id}/reconcile` — import a partner's settlement report
      (CSV/API depending on the partner — confirm per-partner integration method before building,
      see PRD §13 Open Questions) and match against `credit_partner_bills`
- [ ] `GET /api/v1/credit-partners/reconciliation/exceptions` — the three-way mismatch report

## Out of scope

- No credit-limit enforcement logic — explicitly out of scope per the business decision
  documented in PRD §12 ("the partner's own acceptance is the approval gate").
- Live API integration with any specific partner until PRD §13's open question ("which partners
  are actually signed") is answered — build against the generic CSV-import path first.

## Definition of Done

- [ ] A credit-partner sale posts correctly against the partner's BUSY account, with the
      real end-customer still traceable in our own records (test this traceability explicitly).
- [ ] A synthetic settlement report import correctly matches known-good bills and correctly
      flags a deliberately-introduced mismatch (amount off, or a bill missing).
- [ ] Loyalty points for a credit-partner sale accrue to the actual end customer, verified with
      a test — this is the specific thing likely to get built backwards, so it needs its own
      explicit test, not just "it probably works because Sprint 6 works."
