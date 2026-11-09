---
id: TASK-145.7.8
title: 'Switch the legacy upgrade job on in production: dry run, then apply'
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - config
dependencies:
  - TASK-145.7.4
  - TASK-145.8.3
  - TASK-145.8.4
  - TASK-145.8.5
  - TASK-145.8.6
references:
  - decisions/incident-management.md
  - app/features/incident/README.md
parent_task_id: TASK-145.7
priority: medium
type: chore
ordinal: 512000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L8. After the TASK-145.8 cutovers have deployed: one config PR sets [incident_response] upgrade_mode = "dry_run" in production.toml; the human reads the report (blockers listed per Migration rule 7, already_upgraded expected 0); a second PR sets "apply"; the human records the applied report. Then mode back to off or kept for the rerun per the README.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dry-run and apply reports are recorded in the notes with zero blockers left (checks the production part of parent AC #13)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
