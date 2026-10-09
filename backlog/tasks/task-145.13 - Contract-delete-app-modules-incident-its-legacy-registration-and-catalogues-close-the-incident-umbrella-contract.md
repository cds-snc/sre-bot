---
id: TASK-145.13
title: >-
  Contract: delete app/modules/incident, its legacy registration and catalogues;
  close the incident umbrella contract
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.11
  - TASK-145.12
  - TASK-118
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 363000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer E2 of TASK-145. After the earlier layers every incident surface is rebuilt and cut over.

THIS SLICE
- Delete app/modules/incident/ and its entry in the legacy handler registration; delete the incident python-i18n catalogues under app/locales/ once the per-package catalogues carry every key (TASK-118 translator contract, parity gate green for EN and FR).
- Remove every freeze-baseline entry naming app/modules/incident; no baseline grows.
- app/tests/integration/legacy_surface/INVENTORY.md: every incident row points at its response, comms or postmortem handler and its pinning test; surfaces found outside the original inventory are listed with their disposition.
- modules/dev/incident.py and the /sre incident dispatcher in modules/sre are repointed or deleted.
- decisions/incident-management.md Migration: remove the closed tolerances and add a dated Changes line; decisions/migration.md and feature-packages.md Context lines naming modules/incident are updated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/incident/ does not exist; no module imports it; the legacy registration list has no incident entry
- [ ] #2 No freeze baseline names app/modules/incident; the import-linter ignore list has not grown
- [ ] #3 The legacy_surface inventory maps every incident surface to its new handler and pinning test
- [ ] #4 decisions/incident-management.md Migration lists no closed tolerance and carries a dated Changes line
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
