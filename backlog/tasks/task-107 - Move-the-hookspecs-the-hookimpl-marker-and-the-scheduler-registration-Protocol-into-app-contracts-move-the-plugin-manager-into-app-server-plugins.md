---
id: TASK-107
title: >-
  Move the hookspecs, the hookimpl marker and the scheduler registration
  Protocol into app/contracts/; move the plugin manager into app/server/plugins/
status: In Progress
assignee: []
created_date: '2026-09-24 19:58'
updated_date: '2026-10-01 16:58'
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
- [x] #1 Every hookspec, the hookimpl marker, the namespace constant and the BackgroundJobRegistry Protocol live in app/contracts/; app/infrastructure/plugins/ is deleted with no re-export
- [x] #2 The plugin manager lives in app/server/plugins/; grep finds import pluggy only in app/contracts/ and app/server/plugins/
- [x] #3 The marker name, the PluginManager project name and the entry-point group are one constant sourced from project metadata
- [x] #4 Every hookimpl imports hookimpl from contracts; the boot-test hookspec inventory moves with the specs and still passes
- [x] #5 decisions/plugins.md, platform-transports.md and platform-entrypoints.md tolerated lists drop the infrastructure/plugins items in the same PR
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Coordinator. Stack A layers 8a-8d, decomposed on 2026-10-01 because the move cannot fit one PR: the hookspecs reference three non-contract types (the jobs Protocol, the concrete infrastructure i18n registry and spec, the concrete EventDispatcher), the manager's move forces a jobs inversion (jobs sits below server in contract (a)), and a single change would touch about 30 production files across contracts, infrastructure, packages, modules, jobs, server and decisions.

Layers, in dependency order (each independently green and revertible; no shims anywhere, per doc-2):
- TASK-107.1 (8a): BackgroundJobRegistry to contracts/scheduler/. 6 files, about 50 LOC. Contract (a) ignores 12 -> 11.
- TASK-107.2 (8b): I18nResourceSpec to contracts/i18n/ plus I18nResourceRegistrar Protocol. 12 files, about 80 LOC. Contract (b) ignores 57 -> 53.
- TASK-107.3 (8c): FeatureLifecycleSpecs, hookspec/hookimpl markers and the metadata-derived PLUGIN_NAMESPACE to contracts/plugins/; 11 hookimpl imports rewritten; inventory test moves. 19 files, about 190 LOC (11 are one-line swaps). Contract (b) ignores 53 -> 44.
- TASK-107.4 (8d): manager and discovery to server/plugins/, infrastructure/plugins/ deleted, jobs.init takes the registration callable, decision-record tolerated lists and stale register_slack_listeners text fixed. 7 files, about 60 LOC changed (about 200 moved), 8 decision lines.

Import-linter delta across the four: contract (a) 12 -> 11, contract (b) 57 -> 44 (-14 entries: 1 + 4 + 9), contracts (d)/(e)/(f) unchanged, nothing added, 8 contracts kept.

AC map for this task: #1 -> 107.1 + 107.2 (spec types) + 107.3 (specs, marker, constant) + 107.4 (deletion of infrastructure/plugins/); #2 -> 107.4; #3 -> 107.3 (definition) + 107.4 (PluginManager use); #4 -> 107.3; #5 -> 107.4; #6 -> every layer's gates. This task is done when 107.1-107.4 are.

Out of scope, unchanged: entry-point discovery (TASK-110 replaces server/plugins/base.py in place and reads the same PLUGIN_NAMESPACE as the entry-point group), the scheduler runtime (TASK-52 moves jobs/scheduled_tasks.py into server/scheduler/ and may drop the callable parameter), deleting register_event_handlers, EventDispatcher and the EventHandlerRegistrar Protocol (TASK-30).
Rollback per layer: git revert of that layer's PR; layers revert top-down.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
All four layers are implemented (2026-10-01): TASK-107.1 (scheduler registry Protocol, #1521), TASK-107.2 (i18n spec and registrar, #1522), TASK-107.3 (hookspecs, markers, namespace constant, #1523) and TASK-107.4 (plugin manager to server/plugins, infrastructure/plugins deleted, decision records). Gates and evidence are in each subtask's notes. AC #3 caveat: no entry-point group is declared yet (TASK-110), so the constant currently names the two markers and the PluginManager only.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-01 14:59
---
Plan approved 2026-10-01 (Guillaume Charest, in session): decomposition into TASK-107.1 -> TASK-107.2 -> TASK-107.3 -> TASK-107.4 as Stack A layers 8a-8d. Decisions confirmed as planned: register_event_handlers stays in 8c behind the EventHandlerRegistrar Protocol (TASK-30 deletes both); contracts/plugins/ imports FastAPI and structlog BoundLogger at runtime; scheduled_tasks.init takes the registration callable, no new ignore entry; four layers, 8a and 8b not merged. i18n and the scheduler stay framework services (contracts in contracts/, implementations bound for server/), not capabilities, per plugin-architecture.md and i18n.md.
---
<!-- COMMENTS:END -->
