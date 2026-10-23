---
id: TASK-124.4
title: Move packages/talent to app/features/talent/
status: To Do
assignee: []
created_date: 2026-09-24 20:01
updated_date: '2026-10-23T17:32:00Z'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-120
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1669
parent_task_id: TASK-124
priority: low
type: task
ordinal: 270000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. packages/talent was created under migration.md rule 5 as the destination of role logic leaving modules/role. It holds only adapters/google_drive.py, the Drive adapter that modules/role/role.py:10 calls; it has no hookimpls, entry point or settings slice. It moves to app/features/talent/ before the role surface is rebuilt into it (TASK-39), so the rebuild lands in the final path. Behaviour-preserving move; it waits for TASK-120, which repoints the adapter to app/capabilities/drive/api.py, so the adapter moves once onto its final import.

Talent is a feature, not a library: its final shape (subdomains, records through the records contract, entry points) is planned with the role rebuild in TASK-39 and ends in the same layout as the incident feature umbrella (decisions/incident-management.md, feature-packages layout). Low priority: this move is mechanical and waits for that planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/talent/ is moved to app/features/talent/ with adapters/google_drive.py and a README naming its consumer; the TASK-114 package-shape check is green
- [ ] #2 The old packages/talent path is deleted with no re-export; every importer and mock patch string (modules/role/role.py, tests/unit/packages/talent/) is rewritten, and the tests move under tests/unit/features/talent/
- [ ] #3 The import-linter feature-independence contract lists features.talent instead of packages.talent (app/pyproject.toml:336); ignore entries only shrank
- [ ] #4 No entry point, enablement key or settings slice is added; TASK-39 adds them with the rebuilt role surface
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
