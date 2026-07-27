---
id: TASK-6
title: >-
  Replace the PREFIX-gated scheduler with a Tier-2 TTL lease on the
  conditional-write primitive
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-27 15:39'
labels:
  - reliability
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
  - TASK-5.1
  - TASK-5.3
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

app/jobs/scheduled_tasks.py registers jobs across unrelated domains (modules.aws.identity_center/spending, modules.incident, integrations.maxmind/opsgenie/google_workspace, packages.access.sync) - the Tier-2 lease is a cross-cutting scheduler capability, not something owned by any one feature package.

Steps:
1. Consume the generic acquire_lease/release_lease helper in app/infrastructure/idempotency/lease.py (built by TASK-5.3 on top of TASK-5.1's claim/complete/release primitive). Do not import from app/packages/access/sync/ - that package's platform_lock.py is a feature-specific wrapper over the same shared helper, not the helper itself. If a renew-while-running capability is needed beyond acquire/release, add it to infrastructure/idempotency/lease.py so it stays the single shared implementation.
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 17:58
---
TASK-5 was decomposed on 2026-07-24 (single-PR size gate) into TASK-5.1..TASK-5.4; see TASK-5 for the full rationale. This task's dependency has been re-pointed from TASK-5 directly onto TASK-5.1 (the IdempotencyStore claim/complete/release primitive this Tier-2 lease is built on) and TASK-5.3 (the Access Sync platform/user lock rewrite, which produces a lease helper on the same primitive). Consume TASK-5.3's lease helper for the Tier-2 job lease here rather than reimplementing a second lease on top of TASK-5.1 directly - avoid two competing lease implementations on the same conditional-write primitive.
---

created: 2026-07-27 15:39
---
Correction 2026-07-27: TASK-5.3's plan was revised after architecture review - the reusable lease helper is now app/infrastructure/idempotency/lease.py (acquire_lease/release_lease), not code inside app/packages/access/sync/. Description updated so this task's Tier-2 lease imports that infra module directly; the dependency on TASK-5.3 is kept only because TASK-5.3's PR is what delivers lease.py, not because this task should import anything from the access/sync package.
---
<!-- COMMENTS:END -->
