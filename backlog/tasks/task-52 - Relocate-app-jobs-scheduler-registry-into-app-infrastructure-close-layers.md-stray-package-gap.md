---
id: TASK-52
title: >-
  Relocate app/jobs/ scheduler registry into app/infrastructure/ (close
  layers.md stray-package gap)
status: To Do
assignee: []
created_date: '2026-07-27 15:48'
updated_date: '2026-07-28 16:33'
labels:
  - architecture
  - layers
  - reliability
milestone: m-4
dependencies:
  - TASK-6
  - TASK-64
references:
  - decisions/layers.md
  - decisions/reliability.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1356'
priority: medium
ordinal: 80000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/layers.md defines exactly three tiers under app/ (packages -> infrastructure -> integrations, downward-only imports) plus the server/ host process; app/jobs/ is a fourth, undeclared top-level package that fits neither role and is imported sideways/upward by a genuine infrastructure module.

Evidence:
- app/infrastructure/plugins/specs.py:17 does `from jobs import BackgroundJobRegistry` - an infrastructure module importing a Protocol from a package outside the three-tier model. Per layers.md, infrastructure may only import integrations (+ the infrastructure/operations shared-kernel exception); importing from a sibling top-level package like jobs/ is not a sanctioned path.
- app/jobs/models.py defines BackgroundJobRegistry - a scheduler-agnostic registration Protocol. This is capability-shaped (vendor-neutral: 'register a recurring job by name/schedule'), exactly the Path A / infrastructure-capability shape layers.md describes, not feature/domain logic.
- app/jobs/scheduled_tasks.py hosts the generic scheduler bootstrap (init(), safe_run() error-boundary wrapper, _ScheduleBackgroundJobRegistry adapter binding to the schedule library, hook.register_background_jobs dispatch) interleaved with specific job bodies/imports across modules.*, packages.access.sync.*, and integrations.* - a cross-cutting capability several unrelated features depend on, which decisions/layers.md and .github/copilot-instructions.md both say belongs in app/infrastructure/, never in a standalone package.
- decisions/plugins.md: hookspecs are host-owned and centrally defined in app/infrastructure/plugins/specs.py; the Protocol types a hookspec's signature depends on (BackgroundJobRegistry) should live alongside that host-owned surface, not in a separate ad hoc package.

TASK-6 (m-0) already rewrites the Tier-1/Tier-2 lease-gating behavior inside app/jobs/scheduled_tasks.py in place; this task is the structural follow-up that relocates the generic scheduler capability (Protocol + bootstrap/dispatch machinery) into app/infrastructure/, leaving only feature-owned job bodies where their owning code currently lives (modules/ today, migrating to packages/ per decisions/migration.md's own schedule - not blocked on that migration completing). Depends on TASK-6 so the relocation carries forward the corrected lease/Tier classification rather than migrating then immediately rewriting.

This task itself needs a human-approved implementation plan (backlog task edit TASK-XX --plan) via the task-planner workflow before implementation starts, per the single-PR size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The BackgroundJobRegistry Protocol and the generic scheduler bootstrap/dispatch machinery (safe_run wrapper, schedule-library adapter, plugin hook.register_background_jobs call) move from app/jobs/ into app/infrastructure/ (exact module name decided at planning time); app/infrastructure/plugins/specs.py imports BackgroundJobRegistry from app/infrastructure/, not from a top-level jobs package
- [ ] #2 No top-level app/jobs/ package remains outside the packages -> infrastructure -> integrations layer model (plus server/ as the host process); feature-owned job bodies stay with their owning code (modules/ now, packages/ once migrated) rather than in a standalone jobs/ directory
- [ ] #3 import-linter (or an equivalent grep-based check, pending TASK-18) has no exception/baseline entry needed for this import path post-migration
- [ ] #4 Existing scheduler tests (app/tests covering scheduled_tasks.py / BackgroundJobRegistry) pass unchanged in behavior, updated only for the new import paths
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
