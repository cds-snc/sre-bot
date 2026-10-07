---
id: TASK-140.10
title: Confirm before drafting a status update for a security incident
status: In Progress
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-07 19:05'
labels:
  - incident
dependencies:
  - TASK-140.5.3
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 334000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human decision 2026-10-07: the security check sits on drafting, not approval. Drafting sends the incident channel and comms to the model, so for a security incident (or one whose security flag is unknown, such as incidents declared before the flag was stored) the responder must confirm in the status-updates modal, after pressing Draft, that the scribe may read that content. Without the confirmation no model call is made. Drafting stays manual-only for these incidents: any future automatic drafting (TASK-140 timer follow-up) skips them. The security flag is not stored today: IncidentPayload.security_incident (models/incidents.py) is only used to invite the security group at declare (modules/incident/core.py:545) and never written to the incident record. This task stores it on the legacy incident item and reads it through an incident core interface (yes / no / unknown), then gates drafting on it. Likely exceeds the size gate across legacy module, core and scribe; plan as two slices (store and read the flag; confirm before drafting). Updates decisions/incident-management.md, whose Approval bullet still places the second confirmation at approval.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Declaring an incident stores its security flag, and incident core reads it as yes, no or unknown
- [ ] #2 Pressing Draft for a security incident or an unknown flag asks for confirmation in the modal before any model call; declining or closing makes no model call
- [ ] #3 Non-security incidents draft as before, with no confirmation step
- [ ] #4 The draft service refuses a security or unknown-flag draft without the confirmation, so other entry points cannot bypass it
- [ ] #5 decisions/incident-management.md places the security confirmation on drafting, not approval
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (human): split into 140.10.1 (store and read the flag) and 140.10.2 (confirm before drafting) as Stack H layers 5 and 6 directly above #1548; #1548 is not deployed until 140.10.2 merges. Confirmation is a server-driven confirmation view with Confirm and draft / Cancel, one wording for yes and unknown, Draft button unchanged. Layer 5 keeps branch stack-h/task-140.6-status-update-approve (rename not possible with gh stack modify).
<!-- SECTION:NOTES:END -->
