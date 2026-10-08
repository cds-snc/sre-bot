---
id: TASK-140.6
title: >-
  Review and approve a status update in a modal and show its copy-ready
  bilingual text
status: Done
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-08 15:57'
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
From the status-updates modal (TASK-140.5.2) the responder opens the review modal (views.update in place from a Review button) with editable EN and FR fields and the stage; submit approves it: the record moves DRAFT -> APPROVED with the approver, edited text and stage, and stops there. The modal then shows the copy-ready bilingual text, rendered by the default comms profile through a StatusPagePublisher interface in scribe/ (one consumer, decisions/incident-management.md) whose only adapter returns copy-ready text, for the responder to proofread and copy by hand into their product's channel. PUBLISHED is never set by approval: it is a person's confirmation that they posted the text, toggled in the history modal (TASK-140.8). Nothing is posted to the incident channel and nothing is pushed to an external platform. The view submission is a native Bolt listener in scribe/entrypoints/slack.py registered through the TASK-140.2 registrar; it acks with field errors, then calls the service. Per-product profiles and formats come later (DRAFT-10). Coordinator: implemented by TASK-140.6.1 (service) and TASK-140.6.2 (Slack review modal).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The review modal opens from the status-updates modal and edits EN, FR and stage; submit stores the approved record with the approver and edited text
- [x] #2 Both languages must be non-empty to approve; validation errors show in the modal
- [x] #3 After approval the modal shows the copy-ready EN and FR text from the publisher, and nothing is posted to the incident channel
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (TASK-140.4): approve with StatusUpdateStore.transition(replace(draft, state=APPROVED, approver=..., approved_at=..., en=..., fr=..., stage=...), expected_state=DRAFT); publish with expected_state=APPROVED and published_at. A concurrent approval returns PERMANENT_ERROR STATUS_UPDATE_CONFLICT; a repeated identical submit is success. The in-memory fake is packages.incident.core.adapters.in_memory.InMemoryStatusUpdateStore.

2026-10-07 decisions (human): split into 140.6.1 service and 140.6.2 Slack UI, 140.6 is coordinator. Review modal reached by views.update in place from a Review button. Approval stops at APPROVED; PUBLISHED is a user toggle in TASK-140.8. Both languages non-empty means all four fields in each language non-blank after trim. Stage floor enforced at approval (forward only); un-approve/correct is TASK-140.12. next_update_at kept unless the stage changes, then recomputed; fresh drafts (on demand, or TASK-140.11 timer) cover stale times. Copy-ready text: default profile renders structured plain text (label lines, blank line between sections) shown in a preformatted block per language, verify Slack modal support and copy fidelity at implementation; per-platform formats belong to DRAFT-10. Security confirmation moved from approval to drafting: removed former AC #4, now TASK-140.10.

ACs checked 2026-10-08 from the merged subtasks: AC1 by 140.6.2 #1/#3 and 140.6.1 #1; AC2 by 140.6.1 #2 and 140.6.2 #2; AC3 by 140.6.2 #3/#4 and 140.6.1 #4; AC4 by both subtasks' gates (#1555, #1556).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Human clarification 2026-10-07: nothing is ever pushed to an external platform. The flow is draft, review and adjust, approve and save; people then select the approved, saved update and copy and paste it into the system of their choice. Two reasons: the content and the translation need proofreading, and the bot has no access to product teams' platforms. The copy-ready publisher adapter is the whole publishing story for now. The draft comes from TASK-140.5.1 and is rendered by the comms profile from TASK-140.5.2.
---
<!-- COMMENTS:END -->
