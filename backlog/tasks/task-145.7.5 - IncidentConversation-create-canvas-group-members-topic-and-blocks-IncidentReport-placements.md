---
id: TASK-145.7.5
title: >-
  IncidentConversation create, canvas, group members, topic and blocks;
  IncidentReport placements
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/outbound-clients.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 502000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). IncidentConversation gains create(name) (the TASK-145.6.3 ruling: create arrives with the first binding), create_canvas, group_members, set_topic and post with blocks (Slack adapter, fake, parity suite). IncidentReport gains list_placements() and create_from_template(title, placement=None) (Google adapter over list_child_folders, fake). Inert: no caller until L7b and L9a.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each new IncidentConversation method has Slack adapter, fake and parity tests, with not-writable and name_taken errors classified (outbound-clients.md)
- [ ] #2 list_placements and create_from_template(title, placement) have Google adapter and fake tests; placement None keeps today's folder
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
