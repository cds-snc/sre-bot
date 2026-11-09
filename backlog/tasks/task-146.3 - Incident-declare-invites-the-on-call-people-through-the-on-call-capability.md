---
id: TASK-146.3
title: Incident declare invites the on-call people through the on-call capability
status: To Do
assignee: []
created_date: 2026-10-09 16:44
updated_date: '2026-11-09T19:04:00Z'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-146.1
references:
  - https://github.com/cds-snc/sre-bot/issues/1704
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (human, Stack L OQ1): delivered inside TASK-145.7's declare-service subtask (L9a): response depends on capabilities.oncall.api only; a ScheduleSource port in core resolves the chosen placement to a ScheduleReference; its interim adapter reads the placement folder's genie_schedule through the Drive gateway, read only, tolerated with owner TASK-165.1. This task's ACs are checked by that subtask.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T19:00:00Z

---

Re-cut for E2: incident coordination assigns a product lead via the on-call capability when a source is configured and supports manual assignment otherwise. Urgent paging is separate and follows the Pager port after the coordination MVP; avoid coupling this task to coordination internals.

---

created: 2026-11-09T18:37:00Z

---

Stack L OQ assessment 2026-11-09 (OQ1), proposed re-scope: delivered inside TASK-145.7's L9a (inert declare service). Without the catalogue (165.1), the ScheduleReference comes from an incident-owned schedule-source port whose interim adapter reads the chosen placement folder's genie_schedule through the Drive gateway, read only, tolerated with owner TASK-165.1. AC #1 (no Opsgenie in the umbrella) and AC #2 hold.

---
<!-- COMMENTS:END -->
