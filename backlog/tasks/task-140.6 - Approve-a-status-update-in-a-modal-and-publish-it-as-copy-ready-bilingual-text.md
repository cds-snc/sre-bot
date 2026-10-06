---
id: TASK-140.6
title: Approve a status update in a modal and publish it as copy-ready bilingual text
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 19:08'
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
The draft opens in a modal with editable EN and FR fields and the stage; submit approves it (approver recorded) and publishes through a StatusPagePublisher interface in scribe/ (one consumer, decisions/incident-management.md) whose first adapter returns copy-ready bilingual text, rendered by the default comms profile modelled on GC Notify's published incident history, to the approver and posts a short confirmation in the channel. The modal's view submission is a native Bolt listener in scribe's entrypoints/slack.py registered through the TASK-140.2 registrar; it acks with field errors, then calls the service. Security incidents need an explicit second confirmation in the modal. Per-product profiles and real status-page adapters come later (DRAFT-10).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The modal edits EN, FR and stage; submit stores the approved record with the approver and edited text
- [ ] #2 Both languages must be non-empty to approve; validation errors show in the modal
- [ ] #3 The copy-ready publisher returns the formatted EN and FR text and the channel gets one confirmation post when the channel is writable
- [ ] #4 A security incident cannot be approved without the second confirmation
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
