---
id: TASK-140.8
title: >-
  Browse an incident's approved status updates in the status-updates modal and
  reopen their copy-ready text
status: To Do
assignee: []
created_date: '2026-10-07 15:17'
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
The status-updates modal (TASK-140.5.2) lists the incident's approved updates, newest first, with stage, time and approver. Opening one shows its copy-ready EN and FR text, rendered by the default comms profile through the copy-ready publisher (TASK-140.6), so responders can go back to an earlier update and copy it again. Read-only: no record changes and nothing is posted to the incident channel. It replaces the listing half of the legacy /sre incident updates command retired by TASK-140.7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The status-updates modal lists approved updates newest first with stage, approval time in ET/HE and approver
- [ ] #2 Opening an approved update shows its copy-ready EN and FR text, identical to what was shown at approval
- [ ] #3 An incident with no approved updates shows a localized empty state; all strings are in EN and FR catalogues
- [ ] #4 Nothing is written to the store and nothing is posted to the incident channel
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
