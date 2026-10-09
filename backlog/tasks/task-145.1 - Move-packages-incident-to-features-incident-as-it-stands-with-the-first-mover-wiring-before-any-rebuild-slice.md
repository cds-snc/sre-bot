---
id: TASK-145.1
title: >-
  Move packages/incident to features/incident as it stands, with the first-mover
  wiring, before any rebuild slice
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:14'
labels:
  - incident
  - features
  - chore
dependencies:
  - TASK-144
parent_task_id: TASK-145
priority: high
type: chore
ordinal: 351000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A1 of TASK-145, the first slice: the incident umbrella moves from app/packages/incident/ to app/features/incident/ as it stands (core/, scribe/, documents/, drive/, meet/, scheduling/), so every later slice builds in the final home and nothing is renamed at the end. Pure move, no runtime change. Starts once the TASK-144 stack is merged, because those PRs edit scribe files.

THIS SLICE
- app/features/__init__.py (empty namespace) and the umbrella under it; the old path is deleted.
- First-mover wiring: "features" joins the hatch wheel packages, the import-linter root_packages, the ruff known-first-party list, and every contract that names "packages" as a source or forbidden module (no-host-imports, integrations-via-adapters, no-legacy-imports, contracts-leaf, integrations-leaf); the layers contract already lists (features) as an optional layer. feature-independence gains features.incident; the incident-umbrella contract's container becomes features.incident.
- Entry point "incident.scribe" = "features.incident.scribe"; the ignore entries for scribe's Google Docs adapter, the views module's infrastructure.i18n import and the service's integrations.openai import are renamed, never added.
- Every importer and mock patch string rewritten: tests (about 70 files), modules/incident (migration.md rule 5: an import-path change in a frozen module), jobs/scheduled_tasks.py, the legacy_surface registration test. Tests move to tests/unit/features/incident/ and tests/integration/features/incident/ with their names unchanged.
- The umbrella and scribe READMEs, the legacy_surface inventory and decisions/incident-management.md's tolerated list name the new path.
- Not in this slice: the package-shape check (TASK-114), per-environment enablement (TASK-112) and TOML settings (TASK-111) arrive on their own; settings slices and environment variable names are unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/features/incident/ holds core, scribe, documents, drive, meet and scheduling unchanged; app/packages/incident/ does not exist; every importer and patch string is rewritten
- [ ] #2 features is a hatch wheel package, an import-linter root package and a ruff first-party package; every contract naming packages also names features; the umbrella and independence contracts name features.incident
- [ ] #3 The entry point incident.scribe targets features.incident.scribe; the import-linter ignore list only renamed entries and did not grow
- [ ] #4 Tests live under tests/unit/features/incident/ and tests/integration/features/incident/ and pass unchanged apart from paths; the legacy_surface suite passes
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
