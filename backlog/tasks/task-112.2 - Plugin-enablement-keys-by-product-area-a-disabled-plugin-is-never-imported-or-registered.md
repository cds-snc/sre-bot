---
id: TASK-112.2
title: >-
  Plugin enablement keys by product area; a disabled plugin is never imported or
  registered
status: To Do
assignee: []
created_date: '2026-10-23T19:21:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-112.1
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/product-scope.md
  - decisions/lifecycle.md
parent_task_id: TASK-112
priority: medium
type: feature
ordinal: 440000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-112. base.toml gains one [plugins.<area>] table per product area (incident_response, cloud_operations, platform_access, workplace_utilities; decisions/product-scope.md), each mapping an entry-point name to a boolean ("incident.comms" = true), modelled on Backstage's id-to-boolean extension map. A PluginsSettings ConfigurationSlice in server/plugins/settings.py reads the tables as maps; the host never names a plugin in code. The configuration phase fails boot naming the name when an installed entry point has no key, a key names no installed entry point, or a name appears under two areas. load_plugins calls pm.set_blocked for each disabled name before pm.load_setuptools_entrypoints, so a disabled plugin's module is never imported (pluggy skips blocked entry points before ep.load()). The no_plugins_loaded error becomes 'no entry points in the group', so an environment that disables every plugin still boots. All nine keys are true in base except the three access.* keys, which stay false as production runs them today (TASK-112.3 removes their in-code switches); user_rotations sits under incident_response (decisions/oncall.md: rotations are an on-call schedule source). product-scope.md is amended: user_rotations in the incident response row, and enablement switches an area off with a configuration change, not 'without a deploy' (the files are baked into the image).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 base.toml has one [plugins.<area>] table per product-scope area, and every installed entry point has exactly one key; a missing, unknown or duplicated name fails boot naming it (boot tests)
- [ ] #2 A plugin disabled in the environment file is never imported or registered: no routes, no OpenAPI entries, no hookimpl calls, no settings reads (boot test)
- [ ] #3 An environment that disables every plugin boots; an empty entry-point group still fails boot
- [ ] #4 decisions/product-scope.md lists user_rotations under incident response and describes area enablement as a configuration change
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->
