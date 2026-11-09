---
id: TASK-145.9.1
title: >-
  IncidentReport.append_timeline_entry; the legacy timeline rewrite moves into
  core/adapters/google_docs.py
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: feature
ordinal: 516000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10a (slices in TASK-145.9's plan). Mechanical move of incident_document.py 82-302 (build_timeline_replacement included) into core/adapters/google_docs.py behind IncidentReport.append_timeline_entry (and removal), fake and parity test; legacy handlers call the moved function.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 append_timeline_entry has Google Docs adapter, fake and parity tests; the legacy capture pins pass unchanged (checks the move part of parent AC #7)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
