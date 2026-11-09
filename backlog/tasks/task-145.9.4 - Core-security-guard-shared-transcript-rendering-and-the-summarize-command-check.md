---
id: TASK-145.9.4
title: >-
  Core security guard, shared transcript rendering and the summarize command
  check
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.9.3
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: feature
ordinal: 519000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10d. One core security guard used by comms and summarize (comms behaviour and log events unchanged), one core transcript renderer (each prompt's text unchanged), summarize resolves through find_incident_for_conversation and reads the primary binding's conversation; inline baseline lines 10-12 removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Security refusal, rendering and command-check tests pass (checks parent ACs #4, #9, #10, #12)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
