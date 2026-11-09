---
id: TASK-145.9.3
title: Move summarize from scribe into incident.response
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.9.2
  - TASK-25.10.3
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: task
ordinal: 518000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10c (size exception approved 2026-11-09: pure move). summary and its prompt move into response/service/summary.py and prompt.py; scribe loses its summary path, catalogue and test; behaviour unchanged; an optional text-generation use with no requirement in response.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 summarize lives in response/service/; scribe holds no summary path, catalogue or test; make check-package-shape passes with no new baseline entry (checks parent ACs #3, #11)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
