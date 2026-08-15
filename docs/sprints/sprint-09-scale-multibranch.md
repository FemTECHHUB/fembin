# Sprint 9 — Multi-branch Rollout & Scale Hardening

**Goal:** the platform holds up at the real retail target — roughly **100× the data volume**
of the pilot — not just at pilot-branch scale.

**Depends on:** everything before it
**PRD references:** §11 (the whole sprint is essentially executing §11's checklist)

## Scope

- [ ] Roll out to remaining branches (from the 1 pilot branch to the full set — PRD §11 projects ~200)
- [ ] **Load-test the pagination from Sprint 1** against actual retail-scale row counts, not the
      pilot's small dataset — if the pilot never exercised a multi-page sync, this sprint is
      the first time it's really proven
- [ ] Revisit the Item generic-column decoding question (PRD §11): if the catalog is now large
      enough that per-item `GetMasterXML` calls are the bottleneck, decode `Master1`'s `D#`/`C#`
      columns for `MasterType=6` directly (turns N calls into 1 bulk query) — only do this if
      the data actually shows it's needed, don't pre-optimize
- [ ] Postgres indexing pass on every synced table — `(busy_code)`, `(stamp)`,
      `(material_center_code)`, `(date)` at minimum (PRD §11)
- [ ] Queue-depth alerting validated under real multi-branch concurrent load, not just the
      pilot's lighter load from Sprint 5
- [ ] Re-verify NFR5/NFR6 (dedicated account, cashier-in-narration) hold up across many
      simultaneous cashiers, many branches — this was designed for it but needs real confirmation

## Out of scope

- New features — this sprint is entirely about the existing feature set holding up at scale, not
  adding new scope. Resist scope creep here.

## Definition of Done

- [ ] A real (or realistically synthetic) load test at approximately the projected retail volume
      — documented numbers, not "it seemed fine."
- [ ] Queue backlog behavior under sustained load is graceful (visible, alerting fires, nothing
      silently dropped) — deliberately overload it in a test environment and confirm.
- [ ] All branches live, each posting to its correct Material Center, verified by spot-checking
      a sample of real vouchers per branch in BUSY directly.
