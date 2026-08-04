---
id: TASK-64
title: >-
  Widen BackgroundJobRegistry and move lease/error-boundary enforcement into the
  scheduler registry (scheduler-as-clock-driven transport)
status: To Do
assignee: []
created_date: '2026-07-28 16:29'
updated_date: '2026-07-28 17:04'
labels:
  - architecture
  - reliability
  - layers
milestone: m-4
dependencies:
  - TASK-6
references:
  - decisions/reliability.md
  - decisions/plugins.md
  - decisions/platform-transports.md
  - 'https://github.com/cds-snc/sre-bot/issues/1373'
priority: medium
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/reliability.md (Background jobs) + decisions/plugins.md + decisions/platform-transports.md. The scheduler is a clock-driven host capability that should be composed like a transport: the host owns the runtime and features push their own jobs at startup via the register_background_jobs hookspec, exactly as features push routers via register_routes.

Current gap: app/jobs/models.py BackgroundJobRegistry.register(*, job_name, schedule, job) is too narrow to be that push boundary - it accepts a daily .at() string only (no interval expression, no Tier classification, no lease TTL). Because the Protocol cannot express interval jobs (every N minutes/hours) or singleton leasing declaratively, the timing plumbing, the safe_run error boundary, and the Tier-2 lease (_tier2 from TASK-6) are all hand-wired centrally in app/jobs/scheduled_tasks.py::init instead of being applied by the registry. That is why access/sync (the one correct register_background_jobs consumer today) can only register a plain daily job and cannot declare a Tier-2 lease through the boundary.

Scope: widen the registry Protocol and make the scheduler registry adapter (the host-owned runtime) apply the plumbing, so a registration site declares intent only.
- Widen BackgroundJobRegistry.register to carry: (a) a schedule expression rich enough for both interval (every N minutes/hours) and daily-at; (b) Tier classification (Tier-1 run-everywhere vs Tier-2 singleton); (c) optional lease_ttl_seconds for Tier-2. Value types / Protocols only - cross-platform hookspec purity per plugins.md.
- Move safe_run (error boundary) and run_if_leased (Tier-2 lease, from TASK-6's lease.py helpers) enforcement INTO the registry adapter. After this, TASK-6's central _tier2 wrapper in scheduled_tasks.py is deleted and its behavior lives in the adapter; each registration (host-owned or feature hookimpl) supplies tier + ttl + schedule, never a hand-rolled try/finally.
- The two host-owned jobs (scheduler_heartbeat, integration_healthchecks) register as Tier-1 through the same widened path.
- The single shared default lease TTL from TASK-6 stays for now (removed later by TASK-B when the last modules/ job is strangled); this task does NOT yet colocate per-job TTLs into feature settings - that is TASK-B, gated on the modules->packages migration.

Sequencing: TASK-6 (in-place Tier-2 lease, single default TTL) -> THIS TASK (widen the registry + move enforcement into it, in place under app/jobs/) -> TASK-52 (relocate the now-thinner capability into app/infrastructure/) -> TASK-B (strangle the pull-hub as modules/ jobs migrate). TASK-52 is re-pointed to depend on this task so it relocates the widened capability rather than the narrow one.

This task needs its own human-approved implementation plan (backlog task edit <id> --plan) via the task-planner workflow before any code, per the single-PR size gate.

BREAKDOWN GUIDANCE FOR THE PLANNING CODING AGENT: check the single-PR size gate. Widening the Protocol + rewriting the schedule-library adapter + migrating all existing registration sites (2 host Tier-1, 3 modules Tier-2, 1 access/sync hookimpl) plus updating tests may exceed ~400 LOC / one reviewable PR. If so, decompose into safe incremental subtasks, e.g.: (1) widen the Protocol + adapter with a back-compatible shim and migrate the host-owned Tier-1 jobs; (2) migrate the 3 Tier-2 modules jobs onto the widened path and delete _tier2; (3) migrate the access/sync hookimpl to declare its Tier/TTL through the boundary. Keep the schedule-library-adapter rewrite (mechanical) separate from any behavior change where possible (copilot-instructions: do not mix refactor + behavior in one PR).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 BackgroundJobRegistry.register carries a schedule expression covering both interval (every N minutes/hours) and daily-at, a Tier classification (Tier-1 run-everywhere vs Tier-2 singleton), and an optional lease TTL for Tier-2 - value types/Protocols only (plugins.md cross-platform-hookspec purity)
- [ ] #2 The scheduler registry adapter applies the safe_run error boundary and Tier-2 lease enforcement (run_if_leased) centrally; every registration site (host-owned or feature hookimpl) declares tier + ttl + schedule and contains no hand-rolled try/finally or _tier2 wrapper
- [ ] #3 TASK-6's central _tier2 wrapper in scheduled_tasks.py is deleted; its behavior now lives in the registry adapter
- [ ] #4 The two host-owned jobs (scheduler_heartbeat, integration_healthchecks) register as Tier-1 through the widened path; existing Tier-2 jobs are migrated onto it with no behavior change (tests)
- [ ] #5 The single shared default lease TTL from TASK-6 is retained (removed later by TASK-B); this task does NOT colocate per-job TTLs into feature settings
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass (behavior unchanged for existing jobs; new Protocol shape covered)
- [ ] #2 A human-approved implementation plan exists on this task (via task-planner) before any implementation PR opens; planner has checked the single-PR size gate and decomposed if needed
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 16:33
---
Placeholder IDs resolved: 'THIS TASK'/'TASK-A' in the description = TASK-64 (this task); 'TASK-B' = TASK-65 (strangle the pull-hub into feature hookimpls). Predecessor TASK-6 rewritten 2026-07-28 to the minimal single-default-TTL scope; this task delivers the declarative tier/TTL/schedule registry that lets features (and the eventual migrated modules jobs) declare leasing through the boundary.
---
<!-- COMMENTS:END -->
