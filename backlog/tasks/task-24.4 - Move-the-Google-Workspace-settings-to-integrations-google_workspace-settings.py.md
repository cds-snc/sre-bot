---
id: TASK-24.4
title: >-
  Move the Google Workspace settings to
  integrations/google_workspace/settings.py
status: To Do
assignee: []
created_date: '2026-10-19 17:19'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
parent_task_id: TASK-24
priority: medium
ordinal: 402000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-24. A pure move of app/infrastructure/configuration/integrations/google.py (GoogleWorkspaceSettings with its customer-id validator, and GoogleResourcesConfig) to app/integrations/google_workspace/settings.py. Consumers: infrastructure/directory/factory.py, integrations/google_workspace/client.py, packages/talent/adapters/google_drive.py, features/incident/drive and scribe adapters, server/lifespan.py, server/configured_systems.py (its Google TenantSource row), seven legacy modules/ files, and the import-linter ignore entries in pyproject.toml. Whether GoogleResourcesConfig (GOOGLE_RESOURCES) is vendor or feature configuration is decided at planning. Env names, defaults and validation unchanged.

Merge order: after #1722, #1723 and #1728 (Stack K layers 5 to 7, TASK-145.5.4, 145.5.8, 145.5.9) have merged, because server/configured_systems.py (TASK-145.5.9, #1728) imports the old path; moving it first would rebase every open layer (doc-13 approve-latest-push rule). #1728 merges once layer 8 (TASK-145.5.10) is submitted above it. Cut from main after that merge. TASK-145.5.9 is not a recorded dependency only because it exists on the stack branch, not on main; add it with --dep once it is on main.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleWorkspaceSettings lives in app/integrations/google_workspace/settings.py and google.py under app/infrastructure/configuration/integrations/ is deleted; GoogleResourcesConfig has one home, recorded in the PR
- [ ] #2 Every consumer (server/configured_systems.py included), test and import-linter entry points at the new home; env names, defaults and the customer-id validator are unchanged
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
