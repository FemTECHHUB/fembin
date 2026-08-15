# Sprint 5 — Pilot Branch Rollout & Hardening

**Goal:** one real branch goes live on the new system, and the security/reliability gaps we've
been flagging since the research phase actually get closed — not deferred again.

**Depends on:** Sprint 4
**PRD references:** §8 (NFRs), §10 (Phased Rollout), §11 (Scale Planning — the write-latency gap)

## Scope

- [ ] **Measure real BUSY write latency** (`SC=2`) under realistic load — this has been flagged
      three times in the research phase and never actioned. It is a **blocker** for this sprint,
      not optional homework.
- [ ] **NFR7 — connection security:** restrict BUSY's port to the backend's IP only (not "any
      source" as it was left during research); replace the weak BUSY password. Verify both, don't
      just configure and assume.
- [ ] **NFR5:** dedicated BUSY service account (not a human's), its own voucher series, BUSY
      auto-numbering confirmed on
- [ ] Queue-depth monitoring + alerting (NFR-adjacent, and explicitly required at scale per §11) — even at pilot-branch scale, wire this now so it's proven before Sprint 9's multi-branch load
- [ ] One real branch's cashiers using the app for real transactions, in parallel with their
      existing process for a defined trial window (don't cut over cold)
- [ ] A runbook: what to do if BUSY's session drops (it did, repeatedly, during research — see
      `docs/reference/14-command-center.md`) — who reconnects it, how fast, what the queue does
      while it's down (answer: backs up safely, doesn't lose anything, per Sprint 4's DoD)

## Out of scope

- Other branches (Sprint 9).
- Loyalty/credit-partner features (Sprints 6–8).

## Definition of Done

- [ ] Write-latency numbers are documented (not estimated) in `docs/PRD.md` §11, replacing the
      "unmeasured" flag.
- [ ] An external port scan confirms 981 is reachable **only** from the backend's IP.
- [ ] A pilot-branch cashier successfully completes a real end-to-end sale (order → payment →
      BUSY posting → printed receipt) without engineering intervention.
- [ ] The BUSY-session-drop runbook has been tested at least once (deliberately disconnect and
      recover) rather than only written.
