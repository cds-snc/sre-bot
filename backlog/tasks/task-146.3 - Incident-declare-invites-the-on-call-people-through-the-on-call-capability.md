---
id: TASK-146.3
title: Incident declare invites the on-call people through the on-call capability
status: To Do
assignee: []
created_date: '2026-10-09 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-146.1
  - TASK-145.7
parent_task_id: TASK-146
priority: medium
type: feature
ordinal: 367000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 3 of TASK-146, in incident/response after TASK-145.7.

THIS SLICE
- The product catalog's on-call entry becomes a ScheduleReference (system and id) instead of an Opsgenie-specific value; response's declare flow asks capabilities.oncall.api who is on call for it and invites them; no Opsgenie vocabulary remains in the incident umbrella.
- A product with no schedule reference or an unavailable source invites nobody and says so in the announcement; declare never fails on it.
- Tests use the capability's in-memory fake.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No module under the incident umbrella imports integrations.opsgenie or names Opsgenie
- [ ] #2 Declare invites the people the on-call fake returns and continues when the lookup fails
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
