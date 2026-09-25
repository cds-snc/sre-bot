---
id: TASK-52
title: >-
  Move the scheduler runtime from app/jobs/ into app/server/scheduler/ and
  delete app/jobs/
status: To Do
assignee: []
created_date: '2026-07-27 15:48'
updated_date: '2026-09-24 20:06'
labels:
  - architecture
  - layers
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-6
  - TASK-64
  - TASK-107
references:
  - decisions/reliability.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1356'
  - decisions/migration.md
  - decisions/plugin-architecture.md
priority: medium
ordinal: 80000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24. decisions/layers.md was deleted. decisions/migration.md's directory table now gives jobs/ its disposition: "Each job moves to its owning feature or capability and registers through the scheduler contract in contracts/; the runtime moves to server/ and runs each job once across replicas on a coordination lease." decisions/reliability.md: the scheduler is a clock-driven host capability, composed like a transport.

Split of the old jobs/ package:
- The BackgroundJobRegistry Protocol and the register_background_jobs hookspec are the scheduler contract. TASK-107 moves them into app/contracts/ with the other hookspecs.
- The runtime is host code and moves to app/server/scheduler/ here: init(), the safe_run error boundary, the schedule-library adapter, the Tier-2 lease wrapper, shutdown, and the two host-owned Tier-1 jobs (heartbeat, integration health-check sweep).
- The legacy pull-hub's hand-imports of modules/ and packages/ job bodies move with the runtime into server/, which may import everything as the composition root. TASK-65 strangles them job by job as each owning surface is rebuilt.

After this ticket, no app/jobs/ package remains. Depends on TASK-64, so the widened registry moves rather than the narrow one, and on TASK-107, so the contract is already in contracts/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The scheduler runtime (init, safe_run, schedule adapter, Tier-2 lease enforcement, shutdown, heartbeat and health-check jobs) lives in app/server/scheduler/; the BackgroundJobRegistry Protocol is imported from app/contracts/
- [ ] #2 app/jobs/ no longer exists; the remaining legacy job hand-imports live only in app/server/scheduler/ until TASK-65 strangles them
- [ ] #3 import-linter needs no new ignore entry for the moved paths
- [ ] #4 Existing scheduler tests pass unchanged in behavior, updated only for the new import paths
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; PR references decisions/layers.md and cross-references TASK-6
- [ ] #2 A human-approved implementation plan exists on this task (via task-planner) before any implementation PR opens
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 16:33
---
Re-sequenced 2026-07-28 (per the scheduled job architecture review): now also depends on TASK-64 (widen BackgroundJobRegistry + move lease/error-boundary enforcement into the scheduler registry). Order is TASK-6 -> TASK-64 -> TASK-52 so this task relocates the WIDENED, thinner scheduler capability into app/infrastructure/ rather than the narrow registry that would immediately be rewritten. The pull-hub strangle (TASK-65) proceeds after, gated on the m-5 modules->packages migration; TASK-52 does not block on it.
---
<!-- COMMENTS:END -->
