---
id: TASK-140.9
title: Redraft a status update from reviewer instructions in the review modal
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
ordinal: 332000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the review modal (TASK-140.6) the responder can, instead of editing, write instructions for the model (for example 'do not name the vendor', 'say only sign-in is affected'). One model call redrafts the EN and FR fields from the current draft, the same transcript window and the instructions, and the result is stored as a new DRAFT record and shown for review. The instructions steer the fields only: code still owns rendering, the stage floor and the 'nothing new' decision (decisions/incident-management.md). The modal shows a redrafting state while the model runs. Nothing is posted to the incident channel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Submitting instructions makes one model call and stores the redraft as a new DRAFT record that the review modal then shows
- [ ] #2 The instructions are passed to the model as reviewer guidance and the redraft keeps the stage floor and the strict field parsing of the first draft
- [ ] #3 Blank instructions are rejected in the modal; a model failure or unparseable output keeps the previous draft and shows a localized error
- [ ] #4 Nothing is posted to the incident channel; all strings are in EN and FR catalogues
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
