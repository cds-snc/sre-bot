---
id: TASK-140.6
title: >-
  Review and approve a status update in a modal and show its copy-ready
  bilingual text
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-07 15:17'
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
From the status-updates modal (TASK-140.5.2) the responder opens the review modal with editable EN and FR fields and the stage; submit approves it (approver recorded) and publishes through a StatusPagePublisher interface in scribe/ (one consumer, decisions/incident-management.md) whose only adapter returns copy-ready bilingual text rendered by the default comms profile. The modal then shows that text for the responder to proofread and copy by hand into their product's channel. Nothing is posted to the incident channel and nothing is pushed to an external platform. The view submission is a native Bolt listener in scribe/entrypoints/slack.py registered through the TASK-140.2 registrar; it acks with field errors, then calls the service. Security incidents need an explicit second confirmation in the modal. Per-product profiles come later (DRAFT-10); status-page adapters need the no-automatic-publishing decision reassessed first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The review modal opens from the status-updates modal and edits EN, FR and stage; submit stores the approved record with the approver and edited text
- [ ] #2 Both languages must be non-empty to approve; validation errors show in the modal
- [ ] #3 After approval the modal shows the copy-ready EN and FR text from the publisher, and nothing is posted to the incident channel
- [ ] #4 A security incident cannot be approved without the second confirmation
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (TASK-140.4): approve with StatusUpdateStore.transition(replace(draft, state=APPROVED, approver=..., approved_at=..., en=..., fr=..., stage=...), expected_state=DRAFT); publish with expected_state=APPROVED and published_at. A concurrent approval returns PERMANENT_ERROR STATUS_UPDATE_CONFLICT; a repeated identical submit is success. The in-memory fake is packages.incident.core.adapters.in_memory.InMemoryStatusUpdateStore.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Human clarification 2026-10-07: nothing is ever pushed to an external platform. The flow is draft, review and adjust, approve and save; people then select the approved, saved update and copy and paste it into the system of their choice. Two reasons: the content and the translation need proofreading, and the bot has no access to product teams' platforms. The copy-ready publisher adapter is the whole publishing story for now. The draft comes from TASK-140.5.1 and is rendered by the comms profile from TASK-140.5.2.
---
<!-- COMMENTS:END -->
