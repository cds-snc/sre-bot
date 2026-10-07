---
id: TASK-140.10.2
title: >-
  Ask the responder to confirm before drafting a status update for a security or
  unknown-flag incident
status: To Do
assignee: []
created_date: '2026-10-07 19:02'
labels:
  - incident
dependencies:
  - TASK-140.10.1
parent_task_id: TASK-140.10
priority: high
type: feature
ordinal: 340000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-140.10, Stack H layer 6. draft_status_update gains security_confirmed (default False) and an injected IncidentSecurityReader; for a YES or UNKNOWN incident it returns permanent error SECURITY_CONFIRMATION_REQUIRED just before a model call is needed (after the PENDING/CARRIED_FORWARD branches, before on_started), so other entry points and future automatic drafting (TASK-140.11) cannot bypass it; a flag read failure also refuses. The Draft handler then updates the modal to a confirmation view (one wording for yes and unknown: the incident is, or may be, a security incident and drafting sends the channel and comms content to the AI model) with a Confirm and draft button (incident.scribe.status_update.draft_confirmed) and Cancel as the view close; the confirm listener calls the service with security_confirmed=True. The Draft button itself is unchanged. The drafting view moves into on_started so it shows only when a model call is imminent. decisions/incident-management.md moves the security confirmation from approval to drafting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Pressing Draft on a YES or UNKNOWN incident shows the in-modal confirmation view and makes no model call
- [ ] #2 Confirm and draft drafts; Cancel or closing makes no model call
- [ ] #3 A NO incident drafts as before with no confirmation step
- [ ] #4 draft_status_update refuses YES or UNKNOWN without security_confirmed, and refuses on a flag read failure, with no model call and no on_started; PENDING and CARRIED_FORWARD need no confirmation
- [ ] #5 The drafting view appears only when a model call is about to happen
- [ ] #6 New strings exist in EN and FR with matching keys; nothing is posted to the incident channel
- [ ] #7 decisions/incident-management.md places the security confirmation on drafting, not approval
- [ ] #8 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
