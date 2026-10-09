---
id: TASK-36.3
title: Pin the legacy scheduled-job entry points
status: To Do
assignee: []
created_date: '2026-09-28 14:36'
updated_date: '2026-10-09 17:01'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
parent_task_id: TASK-36
priority: high
ordinal: 287000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pin the 5 job entry points that call into modules.aws and modules.incident, plus the 2 plugin-registered jobs, as the before/after check for the TASK-52 scheduler move and the TASK-145 and TASK-88 rebuilds. Invoke each job's entry point directly with faked integrations and assert on its observable effects; do not start the scheduler.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each legacy job entry point in the TASK-36 inventory has a pinning test with faked integrations
- [ ] #2 Tests live in app/tests/integration/legacy_surface/ and run in the normal gate
- [ ] #3 The TASK-36 inventory marks each job row pinned by this task
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
