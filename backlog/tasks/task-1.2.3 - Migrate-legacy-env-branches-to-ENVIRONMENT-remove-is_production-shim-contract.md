---
id: TASK-1.2.3
title: >-
  Migrate legacy env branches to ENVIRONMENT; remove is_production shim
  (contract)
status: To Do
assignee: []
created_date: '2026-07-17 19:47'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.2.2
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-1.2
priority: high
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-1.2 — contract phase. Migrate three legacy modules still using PREFIX-string comparisons for environment decisions, then remove the is_production forwarding shim from AppSettings and Settings. After this slice all environment-conditional code reads ENVIRONMENT directly and the old is_production property no longer exists. dev/platforms/slack.py gates dev commands with PREFIX != dev-; must gate with ENVIRONMENT == dev. incident/core.py derives environment string for DB records from PREFIX == dev-; must read ENVIRONMENT directly. incident_conversation.py sets channel name prefix from PREFIX == dev-; must use ENVIRONMENT == dev. After migrating all callers, remove is_production from infrastructure/configuration/app.py, infrastructure/configuration/settings.py, and clean the is_production parameter from infrastructure/logging/setup.py. Update all test fixtures that still mock is_production (unit/infrastructure/conftest.py, unit/infrastructure/logging/conftest.py, unit/server/conftest.py, test_settings_structure.py).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/dev/platforms/slack.py _require_dev_environment uses ENVIRONMENT == dev; no PREFIX string comparison remains
- [ ] #2 modules/incident/core.py _create_database_record environment string reads app_settings.ENVIRONMENT directly; no PREFIX == dev- comparison remains
- [ ] #3 modules/incident/incident_conversation.py channel name prefix uses ENVIRONMENT == dev; no PREFIX == dev- comparison remains
- [ ] #4 infrastructure/configuration/app.py is_production property removed
- [ ] #5 infrastructure/configuration/settings.py is_production property removed
- [ ] #6 infrastructure/logging/setup.py is_production parameter removed; production mode derives from settings.ENVIRONMENT == production
- [ ] #7 All test fixtures that set settings.is_production = False updated to use ENVIRONMENT explicitly
- [ ] #8 grep -rn is_production app/ --include=*.py returns no hits outside comments or historical strings
- [ ] #9 grep -rn PREFIX app/ --include=*.py returns no environment-derivation hits
- [ ] #10 Full non-smoke test suite passes
<!-- AC:END -->
