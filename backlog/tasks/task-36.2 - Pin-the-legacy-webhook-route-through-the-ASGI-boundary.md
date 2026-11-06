---
id: TASK-36.2
title: Pin the legacy webhook route through the ASGI boundary
status: To Do
assignee: []
created_date: 2026-09-28 14:36
updated_date: '2026-11-06T19:12:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/testing.md
  - decisions/migration.md
  - decisions/webhooks.md
  - https://github.com/cds-snc/sre-bot/issues/1612
parent_task_id: TASK-36
priority: high
ordinal: 286000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pin POST /hook/{webhook_id} (app/api/v1/routes/webhooks.py) through the ASGI boundary with fakes, as the before/after check for the TASK-37.x webhooks rebuild and TASK-53. app/tests/api/v1/test_webhooks.py already gives partial coverage; adopt and extend it into app/tests/integration/legacy_surface/ rather than duplicating it (legacy test files are only edited in place, so leave or delete the old file explicitly, never both copies).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The webhook route's accepted payload families, auth/lookup failures and Slack side effects are pinned through the ASGI app with fakes
- [ ] #2 No duplicate coverage remains between app/tests/api/v1/test_webhooks.py and the legacy_surface suite
- [ ] #3 The TASK-36 inventory marks the webhook row pinned by this task
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Pin task: durable entry points, modal ids read from the opened view, outcome assertions at faked external edges, internal legacy seams only in named legacy_surface/conftest.py fixtures naming the owning rebuild task, legacy_only_* tests for behaviour the rebuild ends.
<!-- SECTION:NOTES:END -->
