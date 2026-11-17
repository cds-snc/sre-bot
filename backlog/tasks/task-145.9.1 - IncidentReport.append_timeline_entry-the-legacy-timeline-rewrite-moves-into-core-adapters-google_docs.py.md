---
id: TASK-145.9.1
title: >-
  IncidentReport.append_timeline_entry; the legacy timeline rewrite moves into
  core/adapters/google_docs.py
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-17T00:25:00Z'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-17 (human, #1858 production fix): re-ground the move at pickup. modules/incident/incident_document.py changed: update_timeline_section returns OperationResult[None] (TIMELINE_UPDATE_ATTEMPTS = 3, re-read before every write, recompute only on a timeout or a refused edit whose re-read shows the revision moved, no sleep), TIMELINE_ENTRY_PATTERN and timeline_message_key (entries keyed by channel + full Slack ts from the permalink), UTF-16 offsets in build_timeline_replacement, lossless extract_timeline_section; apply_document_edits returns OperationResult[None] and keeps SDK retries. The move carries these unchanged into core/adapters/google_docs.py behind append_timeline_entry and its removal; the parity test and the fake keep UTF-16 offsets; the legacy capture pins (two added by #1858: thread reply, bilingual failure notice) pass unchanged.
<!-- SECTION:NOTES:END -->
