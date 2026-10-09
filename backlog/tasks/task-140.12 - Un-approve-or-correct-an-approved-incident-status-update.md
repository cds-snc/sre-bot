---
id: TASK-140.12
title: Un-approve or correct an approved incident status update
status: To Do
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-09 14:09'
labels:
  - incident
dependencies:
  - TASK-140.6
parent_task_id: TASK-140
priority: low
type: feature
ordinal: 336000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deferred (human, 2026-10-08): the current status-update feature is good enough; this task is not planned or implemented yet. Business requirements were settled on 2026-10-08; the implementation plan is written when the task is picked up.

Approval enforces a forward-only stage floor: a draft's stage may not be below the latest approved update's stage. If a responder approves the wrong stage or text, there is no way back today. This task gives responders a way to fix the latest approved update.

## Business requirements (2026-10-08)

- **Fix depends on published**: an approved update not yet marked published (TASK-140.8.2 toggle) can be un-approved back to a draft, fixed and approved again. An update already marked published is fixed by a correction: a new update that supersedes it.
- **Latest approved only**: only the most recent approved update can be un-approved or corrected; older ones are already superseded by later updates.
- **Who and why**: any responder who can approve can un-approve or correct. A short reason is required, recorded, and shown in the history.
- **History keeps the original**: the original stays in the approved-updates history, labelled "Withdrawn" (un-approved) or "Corrected" (superseded) and linked to its replacement, so the history shows what was said publicly.
- **Stage can go back only through a fix**: an un-approval or correction may lower the stage to fix a stage mistake (for example Resolved approved too early). Normal drafts and approvals keep the forward-only stage floor.
- **Public text of a correction**: the copy-ready EN and FR text opens with "Correction:" / "Rectification :" and the date and time of the update it corrects.
- **Next update time**: the re-approved or correcting update sets the next update time. Fixing a wrongly approved Resolved update does not restart periodic drafting (TASK-140.11): it is never resumed automatically, so a responder turns it on again.
- Nothing is posted in the incident channel; all of it happens in the status-updates, review and history modals, as for the rest of TASK-140.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An approved update not yet marked published can be un-approved back to a draft, fixed and approved again
- [ ] #2 An approved update marked published can be corrected by a new update that supersedes it
- [ ] #3 Only the latest approved update can be un-approved or corrected
- [ ] #4 Any responder who can approve can un-approve or correct, and a reason is required and shown in the history
- [ ] #5 The original stays in the history labelled Withdrawn or Corrected and linked to its replacement
- [ ] #6 An un-approval or correction may lower the stage; normal approvals keep the forward-only stage floor
- [ ] #7 A correction's copy-ready EN and FR text opens with Correction / Rectification and the date and time of the corrected update
- [ ] #8 Nothing is posted in the incident channel
- [ ] #9 The fixed update sets the next update time; fixing a wrongly approved Resolved update does not restart periodic drafting, a responder turns it on again
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-09 14:09
---
Vocabulary after TASK-144 (human-first status updates; decisions/incident-management.md 2026-10-09): the review modal is now the status-update form, with Save draft, Approve and, when text generation is configured, "Draft with AI" (with or without instructions; this replaces Redraft). An un-approved update returns to that form as a draft. Every record carries its origin (hand-written, model, model with instructions, carried forward); a correction is a new draft with its own origin. Its "Correction:" wording is rendered by code, never by the model.
---
<!-- COMMENTS:END -->
