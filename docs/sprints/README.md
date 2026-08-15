# Sprint Plan

The [PRD](../PRD.md) describes *what* we're building. This folder breaks it into *when* —
10 sprints, each a bounded, shippable unit of work. Assume ~2 weeks per sprint as a default
planning unit; adjust to actual velocity once Sprint 0–1 are done.

## How to use this with AI agents

- **One sprint = one focused unit of work.** Before starting any task, read `../PRD.md` (the
  relevant section) **and** `../../CLAUDE.md` (engineering rules — non-negotiable) **and** the
  specific sprint file. Don't start coding from the sprint file alone.
- **Definition of Done is not optional.** A sprint isn't finished because the happy path works —
  it's finished when its Definition of Done checklist is fully checked.
- **Don't jump ahead.** Sprint N+1 assumes Sprint N's Definition of Done is met. If it isn't,
  fix that first rather than building on a shaky foundation — this is exactly how technical debt
  starts.
- **Update `../PRD.md`'s Open Questions / this sprint file** if you discover something that
  changes the plan (a BUSY quirk, a wrong assumption) — don't silently work around it.

## Sequence & dependencies

```
Sprint 0  Foundations & Scaffolding
   │
Sprint 1  BUSY Read Layer + Incremental Sync (Catalog)
   │
Sprint 2  Website Sync Completion (WooCommerce push)
   │
Sprint 3  Orders & Checkout Queue ──────────┐
   │                                        │
Sprint 4  Payments & BUSY Posting           │  (3+4 = the app backend's core loop)
   │                                        │
Sprint 5  Pilot Branch Rollout & Hardening ◄┘
   │
   ├── Sprint 6  Loyalty Engine — Core (data model + rules engine)
   │       │
   │   Sprint 7  Loyalty Engine — Redemption & Admin
   │
   └── Sprint 8  Credit Partners & Reconciliation
   │
Sprint 9  Multi-branch Rollout & Scale Hardening
```

Sprints 6–8 can run in parallel with each other (and after Sprint 5) since they're additive to
the core loop, not blocking it. Sprint 9 depends on everything before it.

## Index

| Sprint | Title | PRD §§ |
|---|---|---|
| 0 | [Foundations & Scaffolding](sprint-00-foundations.md) | Migration Plan (§9) |
| 1 | [BUSY Read Layer + Incremental Sync](sprint-01-busy-read-layer.md) | §5, §9, §11 |
| 2 | [Website Sync Completion](sprint-02-website-sync.md) | §5 |
| 3 | [Orders & Checkout Queue](sprint-03-orders-checkout-queue.md) | §6 |
| 4 | [Payments & BUSY Posting](sprint-04-payments-busy-posting.md) | §6, §8 (NFRs) |
| 5 | [Pilot Rollout & Hardening](sprint-05-pilot-rollout-hardening.md) | §8, §10, §11 |
| 6 | [Loyalty Engine — Core](sprint-06-loyalty-core.md) | §7 |
| 7 | [Loyalty Engine — Redemption & Admin](sprint-07-loyalty-redemption-admin.md) | §7 |
| 8 | [Credit Partners & Reconciliation](sprint-08-credit-partners.md) | §12 |
| 9 | [Multi-branch Rollout & Scale Hardening](sprint-09-scale-multibranch.md) | §11 |
