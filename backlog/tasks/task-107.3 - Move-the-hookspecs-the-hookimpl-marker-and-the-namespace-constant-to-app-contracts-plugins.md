---
id: TASK-107.3
title: >-
  Move the hookspecs, the hookimpl marker and the namespace constant to
  app/contracts/plugins/
status: In Progress
assignee: []
created_date: '2026-10-01 14:47'
updated_date: '2026-10-01 16:47'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-107.2
references:
  - decisions/plugins.md
  - decisions/plugin-architecture.md
  - decisions/hookspec-deprecation.md
parent_task_id: TASK-107
priority: high
ordinal: 295000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 8c (slice 3 of TASK-107). FeatureLifecycleSpecs, the hookspec and hookimpl markers move to contracts/plugins/, with one namespace constant derived from project metadata naming both markers. The plugin manager stays in infrastructure/plugins/ for this layer and reads the constant. Every hookimpl importer is rewritten (no re-export of hookimpl from infrastructure.plugins); the hookspec inventory test moves with the specs. register_event_handlers keeps its hookspec, typed on a minimal Protocol, until its own deletion task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 contracts/plugins/ defines FeatureLifecycleSpecs (all six hookspecs, signatures unchanged except the dispatcher and registry types), hookspec, hookimpl and one PLUGIN_NAMESPACE constant read from the installed sre-bot distribution metadata (value stays sre_bot)
- [x] #2 infrastructure/plugins/specs.py is deleted; every hookimpl imports hookimpl from contracts.plugins; infrastructure.plugins exports no hookimpl; rg finds no 'from infrastructure.plugins import hookimpl'
- [x] #3 The 9 contract (b) ignore entries 'packages.* -> infrastructure.plugins' are deleted and no ignore entry is added
- [x] #4 The boot-test hookspec inventory moves to tests/unit/contracts/plugins/ and passes; the TASK-36 legacy_surface suite changes only its marker and namespace imports; no assertion changes
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 8c. Applies decisions/plugins.md (hookspecs are public API in contracts/; plugins import hookimpl from contracts; one namespace constant sourced from project metadata). Mechanical move; the manager stays in infrastructure/plugins/ until layer 8d.

Found call sites:
- Definition: app/infrastructure/plugins/specs.py (83 lines): hookspec = pluggy.HookspecMarker("sre_bot") at :18; FeatureLifecycleSpecs with 6 hookspecs: register_slack_commands(registrar), register_routes(app), register_i18n_resources(registry), register_event_handlers(dispatcher), register_background_jobs(registry), startup_warmup(logger). hookimpl marker: infrastructure/plugins/__init__.py:11 (HookimplMarker("sre_bot")). PluginManager("sre_bot"): manager.py:28.
- Production hookimpl importers (11, all `from infrastructure.plugins import hookimpl`): packages/oncall_sync/__init__.py:19, user_rotations:4, rant:4, access/sync:15, access/request:13, access/catalog:8, incident_summary:12, geolocate:7, incident_draft:12; modules/dev:8, modules/sre:4. Other production importers of the specs: infrastructure/plugins/manager.py:15.
- Test importers (5 files): tests/unit/infrastructure/plugins/test_plugins_hookspecs.py:13-14 (inventory), tests/unit/infrastructure/events/test_hookspec_registration.py:9-10,45, tests/integration/legacy_surface/conftest.py:34,188, tests/integration/infrastructure/hooks/test_i18n_hook_discovery.py:4-5, tests/integration/packages/access/test_access_plugin_discovery_registration.py:7-8.
- import-linter (b): 9 entries "packages.* -> infrastructure.plugins" (catalog, request, sync, geolocate, incident_draft, incident_summary, oncall_sync, rant, user_rotations) delete. modules/ is outside contract (b).

Decisions:
- Hookspec parameter types that are not app code stay as runtime third-party imports (FastAPI, structlog BoundLogger). They cannot go under TYPE_CHECKING: verified on 3.14 that pluggy's add_hookspecs calls inspect.signature, which evaluates lazy annotations and raises NameError. plugins.md already lets routes receive the FastAPI app; plugin-architecture.md:42 ("standard library, typing and pluggy only") is narrower and its text is amended in 8d.
- register_event_handlers keeps its hookspec (no implementers; deleting it belongs to the task that removes the dispatcher and blinker, and hookspec-deprecation.md gates removal). Its dispatcher type becomes a minimal contracts Protocol, EventHandlerRegistrar (register_handler(event_type: str, handler: Callable[[Any], object]) -> None), defined beside the hookspecs; infrastructure.events.EventDispatcher satisfies it structurally. The Protocol is deleted together with the hookspec.
- PLUGIN_NAMESPACE = project name read with importlib.metadata.metadata("sre-bot")["Name"], normalised to the entry-point-group form (hyphen -> underscore), so the value stays "sre_bot" and no existing marker binding changes. A missing distribution raises PackageNotFoundError at import, which matches plugins.md's "must fail loudly". The Dockerfile installs the project (uv sync --locked --no-dev --no-editable), and dev/CI use uv sync, so metadata is present; verify by running the suite and the image build.

Steps:
1. app/contracts/plugins/__init__.py (docstring only, no side effects); namespace.py (PLUGIN_NAMESPACE, hookspec = HookspecMarker(...), hookimpl = HookimplMarker(...)); hookspecs.py (FeatureLifecycleSpecs moved verbatim except the two retyped parameters, plus EventHandlerRegistrar).
2. Delete infrastructure/plugins/specs.py. infrastructure/plugins/__init__.py drops hookimpl and its pluggy import. manager.py imports FeatureLifecycleSpecs and PLUGIN_NAMESPACE from contracts.plugins and builds PluginManager(PLUGIN_NAMESPACE).
3. Rewrite the 11 hookimpl imports to `from contracts.plugins.namespace import hookimpl`.
4. Move the inventory test (below); rewrite the 4 other test imports in place; the legacy_surface conftest builds its PluginManager from PLUGIN_NAMESPACE (import and constant only; no assertion changes).
5. pyproject.toml: delete the 9 contract (b) entries. Add none.

Tests first:
- Move app/tests/unit/infrastructure/plugins/test_plugins_hookspecs.py to app/tests/unit/contracts/plugins/test_contracts_hookspecs_inventory.py (same EXPECTED_HOOKS and EXPECTED_PARAMS; the six hooks and their parameter names are the inventory that proves nothing drifted).
- app/tests/unit/contracts/plugins/test_contracts_plugin_namespace_constant.py: PLUGIN_NAMESPACE == the project metadata name normalised; the markers carry it; a PluginManager built from it binds a hookimpl; AST scan: contracts/plugins imports nothing from the app.
- app/tests/unit/contracts/plugins/test_contracts_event_registrar_protocol.py: the real EventDispatcher is assignable to EventHandlerRegistrar (mypy) and a fake registrar receives register_handler.
- Existing tests in step 4 and the full legacy_surface suite (17 tests) stay green.

Verify: rg "from infrastructure.plugins import hookimpl|infrastructure.plugins.specs" app finds nothing; lint-imports 8 kept, contract (b) 53 -> 44 ignored (after 8b); gates; legacy_surface green before and after.
AC map: #1 steps 1-2 + namespace and inventory tests; #2 steps 2-3 + rg; #3 step 5 + lint-imports; #4 step 4 + inventory test + legacy_surface; #5 gates.
Size: 19 production files (3 new, 1 deleted, 15 edited: __init__.py, manager.py, 11 hookimpls, pyproject.toml), about 190 LOC: about 85 moved, about 35 new, 11 one-line import swaps. One subsystem, no behaviour change. The file count exceeds the gate only through the 11 one-line hookimpl swaps that the no-shim rule requires; a shim split is forbidden by doc-2, so it stays one layer (precedent: 8 hookimpls in TASK-26.1.3).
Blast radius: a missed hookimpl import fails at package import and is logged-and-skipped by auto_discover_plugins, so the feature silently disappears from boot; the plan relies on the rg check and the boot tests test_access_plugin_discovery_registration and test_i18n_hook_discovery to catch it. Rollback: git revert.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From planning (2026-10-01): packages/access/request/__init__.py is touched here for its hookimpl import; fix its stale docstring in the same edit (it still says register_slack_commands(provider); the parameter is registrar since TASK-26.1.3).

Implemented on stack-a/task-107.3-hookspecs-to-contracts (Stack A layer 8c), tests first.

What changed:
- New app/contracts/plugins/: __init__.py (docstring only); namespace.py (PLUGIN_NAMESPACE read from the installed sre-bot distribution metadata and normalised to sre_bot, plus hookspec and hookimpl markers built from it); hookspecs.py (FeatureLifecycleSpecs with all six hookspecs, moved verbatim except register_event_handlers, now typed on the new EventHandlerRegistrar Protocol defined beside it). FastAPI and structlog stay runtime imports, as decided in the plan.
- infrastructure/plugins/specs.py deleted. infrastructure/plugins/__init__.py no longer defines or exports hookimpl. manager.py imports FeatureLifecycleSpecs and PLUGIN_NAMESPACE from contracts.plugins and builds PluginManager(PLUGIN_NAMESPACE).
- The 11 hookimpl importers (9 packages, modules/dev, modules/sre) import hookimpl from contracts.plugins.namespace. No re-export at the old path.
- packages/access/request/__init__.py: stale docstring fixed (register_slack_commands(registrar)), per the planning note.
- pyproject.toml: the 9 contract (b) entries 'packages.* -> infrastructure.plugins' deleted, none added (53 -> 44 ignored).

Tests:
- Inventory test moved to tests/unit/contracts/plugins/test_contracts_hookspecs_inventory.py: imports and the namespace constant only; EXPECTED_HOOKS, EXPECTED_PARAMS and every assertion unchanged. The emptied tests/unit/infrastructure/plugins/ directory is gone.
- New test_contracts_plugin_namespace_constant.py (constant equals the normalised metadata name, both markers carry it, a PluginManager built from it binds a hookimpl, AST scan for app imports outside contracts) and test_contracts_event_registrar_protocol.py (fake registrar, and the real EventDispatcher assigned to the Protocol and delivering an event). 6 new tests.
- tests/unit/infrastructure/events/test_hookspec_registration.py and tests/integration/legacy_surface/conftest.py: import lines, and the conftest builds its PluginManager from PLUGIN_NAMESPACE. No assertion changes. The plan also listed test_i18n_hook_discovery.py and test_access_plugin_discovery_registration.py; they import only infrastructure.plugins.base and .manager, which do not move until 8d, so they are untouched.

Gates (from app/, full ci_code.yml sequence): ruff check clean; make fmt-ci 777 files already formatted; check-sdk-typing OK; check-vendor-package-contract OK (16 baselined); check-aws-platform-seam OK (11 baselined); check-runtime-imports OK; lint-imports 8 kept, 0 broken, contract (b) 44 ignored; make test 2848 passed then 760 passed (legacy_surface included); mypy 65 errors in 22 files repo-wide, error set identical to layer 8b, 0 in touched files.

Verified: rg finds no 'from infrastructure.plugins import hookimpl' and no 'infrastructure.plugins.specs' under app/. Non-editable install check: a scratch venv built with 'uv sync --locked --no-dev --no-editable' (the Dockerfile's command) imports contracts.plugins.namespace and reports sre_bot for the constant, the marker and the manager. No docker image build was run.

Left for 8d as planned: decision records that still name infrastructure/plugins/specs.py (plugins.md, i18n.md, platform-transports.md, platform-entrypoints.md, hookspec-deprecation.md).

Size: 19 production files (3 new, 1 deleted, 15 edited).

Correction to the size line above: 18 production files (3 new, 1 deleted, 14 edited: infrastructure/plugins/__init__.py, manager.py, 11 hookimpls, pyproject.toml); the plan's count of 15 edited was off by one. 15 insertions and 112 deletions in tracked files, plus 111 new lines in contracts/plugins/.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-01 14:59
---
Plan approved 2026-10-01 (Guillaume Charest, in session), as written. See the TASK-107 approval comment for the decisions confirmed across layers 8a-8d.
---
<!-- COMMENTS:END -->
