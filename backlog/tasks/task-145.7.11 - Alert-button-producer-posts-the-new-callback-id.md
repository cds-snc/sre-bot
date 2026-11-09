---
id: TASK-145.7.11
title: Alert-button producer posts the new callback id
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - api
dependencies:
  - TASK-145.7.10
references:
  - decisions/transport-slack.md
parent_task_id: TASK-145.7
priority: medium
type: task
ordinal: 515000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L9c (approved program in TASK-145.7's plan, section 2; outline in the parent plan). api/v1/routes/webhooks.py:173 posts incident.response.alert_buttons; tests/api/v1/test_webhooks.py updated. Merges only once the declare cutover is kept (a later revert of it would strand new-id buttons).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Posted alert buttons carry incident.response.alert_buttons; the legacy alias still serves older messages (checks parent AC #15)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
