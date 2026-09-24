---
id: TASK-107
title: >-
  Move the hookspecs, the hookimpl marker and the scheduler registration
  Protocol into app/contracts/; move the plugin manager into app/server/plugins/
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-106
  - TASK-26.1
references:
  - decisions/plugins.md
  - decisions/plugin-architecture.md
  - decisions/hookspec-deprecation.md
priority: high
type: task
ordinal: 249000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md:
- hookspecs are public API and live in app/contracts/;
- plugins import hookimpl from contracts, never from pluggy;
- one namespace constant, sourced from project metadata, names the HookspecMarker, the HookimplMarker, the PluginManager and the entry-point group;
- no `import pluggy` outside contracts/ and the host's plugin manager in server/.

Today app/infrastructure/plugins/ holds specs.py, the hookimpl marker, get_plugin_manager and auto_discover_plugins; the marker is "sre_bot" in code while [project] name is sre-bot. specs.py imports BackgroundJobRegistry from app/jobs/models.py. That Protocol is the scheduler contract (decisions/migration.md: jobs register through the scheduler contract in contracts/), so it moves here too, or contracts would import jobs.

Depends on TASK-26.1 so the Slack registration hookspecs already take the registrar Protocol rather than Bolt objects. They can then move with every other hookspec in one step, and no hookspec is left behind in infrastructure/.

Out of scope: discovery through entry points (its own ticket) and the scheduler runtime (TASK-52). Mechanical: every hookimpl import and patch string is rewritten, and app/infrastructure/plugins/ is deleted with no re-export.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every hookspec, the hookimpl marker, the namespace constant and the BackgroundJobRegistry Protocol live in app/contracts/; app/infrastructure/plugins/ is deleted with no re-export
- [ ] #2 The plugin manager lives in app/server/plugins/; grep finds import pluggy only in app/contracts/ and app/server/plugins/
- [ ] #3 The marker name, the PluginManager project name and the entry-point group are one constant sourced from project metadata
- [ ] #4 Every hookimpl imports hookimpl from contracts; the boot-test hookspec inventory moves with the specs and still passes
- [ ] #5 decisions/plugins.md, platform-transports.md and platform-entrypoints.md tolerated lists drop the infrastructure/plugins items in the same PR
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
