---
id: TASK-83.8
title: Resolve Slack callers to people at the entry point in shadow mode
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.7
  - TASK-26
references:
  - decisions/platform-entrypoints.md
  - decisions/observability.md
parent_task_id: TASK-83
priority: medium
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/platform-entrypoints.md (Draft) moves caller resolution to the platform entry point in app/server/<platform>/.

In shadow mode, handlers receive the resolved person as optional context, but no behavior changes, so resolution coverage can be measured safely. This depends on TASK-26 being re-scoped to, and completed under, the entry point split.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Slack entry point resolves each caller's account and passes handlers the resolved person or an unlinked marker
- [ ] #2 No handler changes its behavior based on the result
- [ ] #3 Resolution outcomes (resolved, unlinked, unknown account) are counted in logs or metrics using ids only, never emails or names
- [ ] #4 A setting disables resolution entirely
- [ ] #5 Full test suite, ruff and mypy pass
<!-- AC:END -->
