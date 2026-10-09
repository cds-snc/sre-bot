---
id: TASK-38.8
title: >-
  Contract: delete app/modules/incident, its legacy registration and catalogues;
  close the incident umbrella contract
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-09 17:00'
labels:
  - migration
  - phase-5
  - incident
  - superseded
milestone: m-5
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
parent_task_id: TASK-38
priority: medium
ordinal: 313000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SUPERSEDED (2026-10-09) by TASK-145.12: same slice, re-cut for the response | comms | postmortem subdomains, the interim store in packages/incident and the five roles. This task is kept as history and is not to be planned or implemented.

Slice 8 of TASK-38 (contract). After slices 3 to 7 every surface in the TASK-36 inventory assigned to app/features/incident/ is rebuilt and cut over.

THIS SLICE
- Delete app/modules/incident/ and its entry in _register_legacy_handlers(); delete the incident python-i18n catalogues under app/locales/ once the per-package catalogues carry every key (TASK-118 translator contract, TASK-21 parity gate green for EN and FR).
- Remove every freeze-baseline entry naming app/modules/incident; no baseline grows.
- app/tests/integration/legacy_surface/INVENTORY.md: every incident row points at its features/incident/ handler and its pinning test; the five surfaces found outside the inventory on 2026-10-02 (canvas, source-alert bookmark, floppy-disk handlers, recreate-missing-resources, the stubbed updates command) are listed with their disposition.
- decisions/incident-management.md Migration: remove the closed tolerances and add a dated Changes line; decisions/migration.md and feature-packages.md Context lines that name modules/incident or the deleted packages are updated.
- The features.incident layers contract is exhaustive with lifecycle | retrospective | scribe above core above common and no ignore entry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/incident/ is deleted, its legacy list entry is removed, and no freeze baseline names a modules/incident path
- [ ] #2 EN and FR parity is green for every features/incident/ catalogue and the incident python-i18n catalogues are deleted
- [ ] #3 INVENTORY.md maps every incident surface, including the five found outside the inventory, to its rebuilt handler and pinning test
- [ ] #4 decisions/incident-management.md, migration.md and feature-packages.md no longer list a closed incident tolerance; each has a dated Changes line
- [ ] #5 The full legacy_surface suite, ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries only shrank
<!-- AC:END -->
