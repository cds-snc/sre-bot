---
id: TASK-107.1
title: >-
  Move the BackgroundJobRegistry scheduler Protocol from app/jobs/ to
  app/contracts/scheduler/
status: To Do
assignee: []
created_date: '2026-10-01 14:47'
updated_date: '2026-10-01 14:59'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-26.1.3
references:
  - decisions/plugins.md
  - decisions/migration.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-107
priority: high
ordinal: 293000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 8a (slice 1 of TASK-107). Mechanical move of the BackgroundJobRegistry Protocol so the hookspecs can move to contracts/ without contracts importing jobs. Every importer is rewritten; app/jobs/models.py is deleted with no re-export.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/scheduler/ defines BackgroundJobRegistry (register_daily, register_interval) unchanged in signature; app/jobs/models.py is deleted and jobs/__init__.py re-exports nothing
- [ ] #2 infrastructure/plugins/specs.py and jobs/scheduled_tasks.py import it from contracts.scheduler; rg finds no 'from jobs import BackgroundJobRegistry' or 'jobs.models'
- [ ] #3 The contract (a) ignore entry 'infrastructure.plugins.specs -> jobs' is deleted and no ignore entry is added
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 8a. Applies decisions/migration.md (jobs register through the scheduler contract in contracts/) and decisions/plugin-architecture.md (contracts is a leaf). Mechanical move, no behaviour change.

Found call sites (rg, 2026-10-01):
- Definition: app/jobs/models.py:6 (BackgroundJobRegistry; register_daily, register_interval). Re-export: app/jobs/__init__.py:3,5.
- Production importers (3): app/infrastructure/plugins/specs.py:16 (`from jobs import BackgroundJobRegistry`, used at :70), app/jobs/scheduled_tasks.py:13 (subclassed at :30), app/jobs/__init__.py.
- Test importers: none import the Protocol; tests/unit/jobs/test_scheduled_tasks.py:13 imports only _ScheduleBackgroundJobRegistry.
- import-linter: pyproject.toml:226 "infrastructure.plugins.specs -> jobs" is the only entry this removes.

Steps:
1. app/contracts/scheduler/__init__.py (empty docstring only) and app/contracts/scheduler/registry.py: BackgroundJobRegistry copied verbatim from jobs/models.py (typing, collections.abc, datetime only).
2. Delete app/jobs/models.py. app/jobs/__init__.py keeps its docstring and drops the import and __all__.
3. app/jobs/scheduled_tasks.py:13 and app/infrastructure/plugins/specs.py:16 import from contracts.scheduler.registry.
4. app/pyproject.toml: delete the "infrastructure.plugins.specs -> jobs" entry from contract (a). Add none.

Tests first:
- app/tests/unit/contracts/scheduler/test_scheduler_contracts_registry_protocol.py: a fake registry with the two keyword-only methods satisfies the Protocol (mypy-checked assignment plus a call through it); AST scan: contracts/scheduler imports only stdlib.
- Existing tests/unit/jobs/test_scheduled_tasks.py (TestScheduleBackgroundJobRegistry) stays green unchanged.

Verify: rg "jobs.models|from jobs import" app finds nothing; lint-imports 8 kept, contract (a) 12 -> 11 ignored imports; gates.
AC map: #1 steps 1-2 + the Protocol test; #2 step 3 + rg; #3 step 4 + lint-imports; #4 gates.
Size: 6 production files (2 new, 1 deleted, 3 edited), about 50 LOC of which about 35 moved verbatim. One subsystem.
Blast radius: type-only; the runtime registry in jobs is untouched. Rollback: git revert restores the old module.
Assumption: nothing outside app/ (scripts, terraform) imports jobs.models; verify with rg over the repo root.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-01 14:59
---
Plan approved 2026-10-01 (Guillaume Charest, in session), as written. See the TASK-107 approval comment for the decisions confirmed across layers 8a-8d.
---
<!-- COMMENTS:END -->
