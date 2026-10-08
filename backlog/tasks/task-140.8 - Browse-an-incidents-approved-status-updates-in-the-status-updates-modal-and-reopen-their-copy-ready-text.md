---
id: TASK-140.8
title: >-
  Browse an incident's approved status updates in the status-updates modal and
  reopen their copy-ready text
status: To Do
assignee: []
created_date: '2026-10-07 15:17'
updated_date: '2026-10-08 15:56'
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
- [x] #1 The status-updates modal lists approved updates newest first with stage, approval time in ET/HE, approver and published state
- [x] #2 Opening an approved update shows its copy-ready EN and FR text, identical to what was shown at approval
- [x] #3 An incident with no approved updates shows a localized empty state; all strings are in EN and FR catalogues
- [ ] #4 A published toggle moves an update between APPROVED and PUBLISHED, recording published_at and who set it, and can be undone; it is the only store write
- [ ] #5 Nothing is posted to the incident channel
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (human): PUBLISHED is a user confirmation, not set by approval; added the published / not published toggle (undoable). Verify StatusUpdateStore.transition allows PUBLISHED -> APPROVED for the undo.

2026-10-07 decisions (human): split at the size gate into 140.8.1 (list + reopen, scribe only; ACs 1, 2, 3, 5, 6) and 140.8.2 (published toggle incl. core published_by and PUBLISHED -> APPROVED; ACs 4, 5, 6). 140.8 is coordinator with no branch; its ACs are checked as the slices verify them. Open an update in place with a Back button (not views.push); undo clears published_at and published_by; one get_status_update_overview with get_pending_status_update delegating; draft-result and approval views unchanged; list capped at 50 rows with a localized note.

ACs 1-3 checked 2026-10-08 from 140.8.1 #1-#3 (merged, #1557). AC4 (published toggle) is 140.8.2 (#1558, open); AC5 and AC6 also cover 140.8.2's code, so they wait for that merge.
<!-- SECTION:NOTES:END -->
