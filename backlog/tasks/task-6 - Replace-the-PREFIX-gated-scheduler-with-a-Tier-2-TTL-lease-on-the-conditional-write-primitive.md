---
id: TASK-6
title: >-
  Replace the PREFIX-gated scheduler with a Tier-2 TTL lease on the
  conditional-write primitive
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:56'
labels:
  - reliability
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
  - TASK-5
references:
  - decisions/reliability.md
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1260'
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md (Background jobs) and claude-research-outcome.md. Today singleton background jobs are prevented from double-firing across the 2 ECS tasks by an environment-shaped gate in _start_scheduled_tasks at app/server/lifespan.py:105 (if app_settings.PREFIX != "") - the not-yet-migrated state.

Steps:
1. Add a lease helper on top of the IdempotencyStore conditional-write primitive from task-5: acquire(name, ttl) -> bool via conditional write; renew while running; lease expiry allows takeover.
2. Classify each registered job Tier-1 (safe to run on every replica - runs everywhere, no lease) or Tier-2 (singleton - takes the lease before each run).
3. The lease is a duplication optimization, never a correctness mechanism: each Tier-2 job body must be idempotent regardless (document per job).
4. Delete the PREFIX/environment gate in app/server/lifespan.py; keep desired_count=2 for HA.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tier-2 jobs acquire a TTL lease via conditional write before executing; a second replica skips while the lease is held (test with the in-memory fake)
- [ ] #2 An expired lease is taken over by the next runner (test)
- [ ] #3 The scheduler-gating conditional on PREFIX/environment in app/server/lifespan.py is deleted
- [ ] #4 Each Tier-2 job has a one-line idempotency note at its registration site
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; both replicas can boot with jobs enabled in a local two-process check
- [ ] #2 PR references decisions/reliability.md (Background jobs)
<!-- DOD:END -->
