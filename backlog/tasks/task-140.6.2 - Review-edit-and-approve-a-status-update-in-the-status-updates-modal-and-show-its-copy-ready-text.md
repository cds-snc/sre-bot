---
id: TASK-140.6.2
title: >-
  Review, edit and approve a status update in the status-updates modal and show
  its copy-ready text
status: To Do
assignee: []
created_date: '2026-10-07 18:52'
labels:
  - incident
dependencies:
  - TASK-140.6.1
parent_task_id: TASK-140.6
priority: high
type: feature
ordinal: 338000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack slice of TASK-140.6. A Review button beside Draft on views showing a DRAFT (value carries incident_id and sequence) replaces the status-updates modal in place (views.update with view id and hash) with the review modal: stage select and the four EN and four FR fields prefilled. The view submission listener (scribe/entrypoints/slack.py, registered through the TASK-140.2 registrar) acks with response_action errors for invalid fields, otherwise acks with a saving view, calls approve_status_update and updates the view to the copy-ready text: one preformatted block per language under EN and FR headings (verify modal support and copy fidelity). Errors show as an in-modal error view with Close. Label builders and t() stay in scribe/platforms/slack.py. Nothing is posted to the incident channel. Real-provider dispatch coverage for the block action and the view submission, as for the 1d7db039 command-dispatch fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Review button opens the review modal in place with the draft's EN, FR and stage prefilled
- [ ] #2 Submitting with a blank field shows field errors in the modal and does not call the service
- [ ] #3 A valid submit approves the record and the modal shows the copy-ready EN and FR text; service refusals and conflicts show an in-modal error with Close
- [ ] #4 No message is posted to the incident channel
- [ ] #5 Block action and view submission dispatch through a real SlackPlatformProvider in an integration test
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
