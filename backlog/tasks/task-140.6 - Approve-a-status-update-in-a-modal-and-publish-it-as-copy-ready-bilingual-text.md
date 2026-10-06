---
id: TASK-140.6
title: Approve a status update in a modal and publish it as copy-ready bilingual text
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
labels:
  - incident
dependencies:
  - TASK-140.2
  - TASK-140.5
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 325000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The draft opens in a modal with editable EN and FR fields and the stage; submit approves it (approver recorded) and publishes through a StatusPagePublisher interface whose first adapter returns copy-ready bilingual text to the approver and posts a short confirmation in the channel. Security incidents need an explicit second confirmation in the modal. Real status-page adapters come later.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The modal edits EN, FR and stage; submit stores the approved record with the approver and edited text
- [ ] #2 Both languages must be non-empty to approve; validation errors show in the modal
- [ ] #3 The copy-ready publisher returns the formatted EN and FR text and the channel gets one confirmation post when the channel is writable
- [ ] #4 A security incident cannot be approved without the second confirmation
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
