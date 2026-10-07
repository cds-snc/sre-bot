---
id: TASK-140.8
title: >-
  Browse an incident's approved status updates in the status-updates modal and
  reopen their copy-ready text
status: To Do
assignee: []
created_date: '2026-10-07 15:17'
updated_date: '2026-10-07 18:53'
labels:
  - incident
dependencies:
  - TASK-140.6
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 331000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The status-updates modal (TASK-140.5.2) lists the incident's approved updates (APPROVED and PUBLISHED), newest first, with stage, time, approver and whether it was published. Opening one shows its copy-ready EN and FR text, rendered by render_copy_ready from TASK-140.6.1, so responders can go back to an earlier update and copy it again. A published / not published toggle records a person's confirmation that they posted the text to their platform (APPROVED <-> PUBLISHED, with published_at and who set it); it can be undone if the text was not actually posted. Approval never sets PUBLISHED (TASK-140.6). Nothing is posted to the incident channel. It replaces the listing half of the legacy /sre incident updates command retired by TASK-140.7. The toggle may push this past the size gate; check when planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The status-updates modal lists approved updates newest first with stage, approval time in ET/HE, approver and published state
- [ ] #2 Opening an approved update shows its copy-ready EN and FR text, identical to what was shown at approval
- [ ] #3 An incident with no approved updates shows a localized empty state; all strings are in EN and FR catalogues
- [ ] #4 A published toggle moves an update between APPROVED and PUBLISHED, recording published_at and who set it, and can be undone; it is the only store write
- [ ] #5 Nothing is posted to the incident channel
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (human): PUBLISHED is a user confirmation, not set by approval; added the published / not published toggle (undoable). Verify StatusUpdateStore.transition allows PUBLISHED -> APPROVED for the undo.
<!-- SECTION:NOTES:END -->
