---
id: TASK-5.3
title: >-
  Idempotency: rewrite Access Sync platform/user concurrency lock onto
  claim/complete/release; align with TASK-6
status: To Do
assignee: []
created_date: '2026-07-24 17:57'
updated_date: '2026-07-24 19:29'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1350'
parent_task_id: TASK-5
priority: high
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of the TASK-5 decomposition (see TASK-5 for full rationale). Depends on TASK-5.1 (the claim/complete/release primitive and in-memory fake).

Aligns with decisions/reliability.md (Idempotency - concurrency locking is a lease, the same conditional-write contract, but a distinct capability from dedup).

Scope: app/packages/access/sync/platform_lock.py (check_lock/acquire_lock/release_lock) implements a per-platform/per-user sync-job lock via get-then-set on the same racy IdempotencyService (same TOCTOU bug as the Slack case, different symptom). Rewrite it as a lease on the atomic claim primitive from TASK-5.1. Update call sites in app/packages/access/sync/interactions/ingress.py and app/packages/access/sync/job_runner.py and their tests.

Coordination with TASK-6 ("Replace the PREFIX-gated scheduler with a Tier-2 TTL lease on the conditional-write primitive", already depends on TASK-5): TASK-6's Tier-2 job lease and this access-sync lock are both leases on the same new primitive. Avoid two competing lease implementations - add a coordination note/comment in this subtask's code pointing at TASK-6, and wire TASK-6's dependency onto this subtask (done from this side via backlog task edit) so its Tier-2 job lease consumes the lease helper this subtask produces rather than reimplementing one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 check_lock/acquire_lock/release_lock in app/packages/access/sync/platform_lock.py use the atomic claim primitive from TASK-5.1 instead of get-then-set on IdempotencyService
- [ ] #2 app/packages/access/sync/interactions/ingress.py and job_runner.py call sites and their tests are updated to the new lock API
- [ ] #3 TASK-6 has a dependency wired onto this subtask and a comment explaining it should consume this subtask's lease helper rather than reimplementing one
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass, including a concurrency test proving the TOCTOU race is closed for the platform/user lock
- [ ] #2 PR references decisions/reliability.md and cross-references TASK-6
<!-- DOD:END -->
