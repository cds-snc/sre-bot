---
id: TASK-120
title: >-
  Move the drive provider from app/infrastructure/drive/ to the
  app/capabilities/drive/ workplace capability
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - capabilities
  - workplace-systems
milestone: m-7
dependencies:
  - TASK-106
  - TASK-110
  - TASK-114
references:
  - decisions/workplace-systems.md
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/cloud-portability.md
priority: medium
type: task
ordinal: 262000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/workplace-systems.md and plugin-architecture.md: workplace systems (directory, documents, files, spreadsheets, calendar, mail) are capabilities, not infrastructure. infrastructure/ is hosting-only. Their public surface is api.py (the Protocol, domain types and provider function) plus an optional hookspecs module; everything else is private. The Google implementation becomes adapters/google.py, the only file importing app.integrations.google_workspace.

Today app/infrastructure/drive/ exposes a vendor-neutral Protocol with a single Google implementation behind a cached factory, re-exported through a barrel __init__.py.

Scope:
- move the package into the feature-packages shape (api.py, adapters/, settings.py, README.md with its classification and named feature consumers, and a fake);
- repoint every consumer to api.py;
- delete app/infrastructure/drive/ with no re-export.
Behaviour-preserving. migration.md rule 6: the capability is not widened to reproduce legacy conventions, and legacy modules keep calling what they call today until their surface is rebuilt, except for import-path changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/drive/ matches the feature-packages layout for a capability (the TASK-114 shape check is green); its README states the classification and at least one feature consumer
- [ ] #2 Consumers import only app/capabilities/drive/api.py; only its adapters/ import app.integrations
- [ ] #3 An in-memory fake of the api.py Protocol lives in the package and is exercised by tests, as the cloud-portability.md fake contract requires for externally facing capability Protocols
- [ ] #4 app/infrastructure/drive/ is deleted with no re-export; grep finds no import of the old path, including mock patch strings
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
