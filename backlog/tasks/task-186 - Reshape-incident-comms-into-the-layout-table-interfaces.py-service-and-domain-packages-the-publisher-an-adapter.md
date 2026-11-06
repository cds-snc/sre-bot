---
id: TASK-186
title: >-
  Reshape incident/comms into the layout table: interfaces.py, service and
  domain packages, the publisher an adapter
status: To Do
assignee: []
created_date: '2026-11-06T02:57:00Z'
labels:
  - incident
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-114.1
references:
  - decisions/feature-packages.md
  - decisions/incident-management.md
ordinal: 489000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-145.4 carried the status-update modules into features/incident/comms/ flat (approval, comms_profile, form, history, ports, prompt, publisher). The layout table amended on 2026-11-06 (TASK-114.1) gives them homes: the Protocols the service depends on move from ports.py to interfaces.py ('Port' stays out of names); the service helpers move into a service/ or domain/ package; the publisher, which calls Slack, becomes an adapter. A mechanical move with importers and tests repointed and no behaviour change. Single PR from main; it removes comms' entries from app/bin/baselines/package_shape.txt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/comms/ holds only names from the amended layout table; its package_shape baseline entries are deleted
- [ ] #2 Every importer and test is repointed; no behaviour changes (the comms tests pass unchanged apart from import paths)
- [ ] #3 Ruff, import contracts, check-package-shape, mypy and pytest pass
<!-- AC:END -->
