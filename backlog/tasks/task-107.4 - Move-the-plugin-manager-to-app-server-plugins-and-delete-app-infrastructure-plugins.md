---
id: TASK-107.4
title: >-
  Move the plugin manager to app/server/plugins/ and delete
  app/infrastructure/plugins/
status: To Do
assignee: []
created_date: '2026-10-01 14:47'
updated_date: '2026-10-01 14:59'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-107.3
references:
  - decisions/plugins.md
  - decisions/plugin-architecture.md
  - decisions/platform-transports.md
  - decisions/platform-entrypoints.md
parent_task_id: TASK-107
priority: high
ordinal: 296000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 8d (slice 4 of TASK-107, the contract step). get_plugin_manager, auto_discover_plugins, collect_feature_i18n_resources, register_feature_integrations and discover_and_init_features move to server/plugins/; PluginManager is built from PLUGIN_NAMESPACE; app/infrastructure/plugins/ is deleted with no re-export. jobs/scheduled_tasks.py can no longer import the manager (jobs is below server), so lifespan passes the background-job registration callable to scheduled_tasks.init. The tolerated-lists text in the decision records is updated in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 server/plugins/ holds the manager and discovery code; app/infrastructure/plugins/ no longer exists; rg finds no 'infrastructure.plugins' in app/ code or tests
- [ ] #2 rg finds 'import pluggy' / 'from pluggy' only in app/contracts/ and app/server/plugins/ in production code; server/lifespan.py takes its PluginManager type from server.plugins
- [ ] #3 PluginManager, both markers and the entry-point group name are the single PLUGIN_NAMESPACE constant
- [ ] #4 jobs/scheduled_tasks.py imports nothing from server or pluggy; scheduled_tasks.init receives the registration callable and the registered hooks fire exactly as before
- [ ] #5 decisions/plugins.md, platform-transports.md, platform-entrypoints.md, i18n.md, hookspec-deprecation.md and transport-slack.md drop the infrastructure/plugins tolerated items and the register_slack_listeners / provider-typed hookspec text in the same PR
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 8d (contract step). Applies decisions/plugins.md (pluggy confined to contracts/ and the host's plugin manager in server/; one namespace constant) and decisions/plugin-architecture.md (server/ owns the plugin manager). Mechanical move plus one forced dependency inversion in jobs.

Found call sites:
- Today app/infrastructure/plugins/ holds __init__.py (re-exports), base.py (auto_discover_plugins), manager.py (get_plugin_manager, collect_feature_i18n_resources, register_feature_integrations, discover_and_init_features). app/server/ holds body_size_middleware.py, bot_middleware.py, lifespan.py, server.py; no plugins/ yet.
- Production importers of the manager (2): app/server/lifespan.py:35-39 (auto_discover_plugins, get_plugin_manager, register_feature_integrations; also `from pluggy import PluginManager` at :9, used in _initialize_translation_service) and app/jobs/scheduled_tasks.py:11 (get_plugin_manager, called at :113).
- Test importers: tests/integration/infrastructure/hooks/test_i18n_hook_discovery.py:4-5, tests/integration/packages/access/test_access_plugin_discovery_registration.py:7-8, tests/unit/infrastructure/events/test_hookspec_registration.py:9,45 (patch string "infrastructure.plugins.manager.get_plugin_manager"), tests/unit/jobs/test_scheduled_tasks.py:295,326,369 (patch "jobs.scheduled_tasks.get_plugin_manager").
- pluggy imports in production after 8c: infrastructure/plugins/{base,manager,__init__}.py and server/lifespan.py:9 (plus contracts/plugins). Packages only mention pluggy in docstrings.
- Prose: infrastructure/plugins is named in decisions/plugins.md:15,18,90, platform-transports.md:73-74, platform-entrypoints.md:22,66, i18n.md:56, hookspec-deprecation.md:12,25, transport-slack.md:66.

Decisions:
- The move belongs in its own layer, after the contracts move: it rewrites different importers (2 production files), and the contracts layer needs no manager change beyond the constant.
- No re-export, no shim: server/plugins/__init__.py is docstring only; importers use server.plugins.manager and server.plugins.base. Module names are kept so TASK-110 replaces discovery in place.
- jobs is below server in contract (a), so jobs/scheduled_tasks.py cannot import server.plugins and no ignore entry is added. Instead lifespan passes the registration callable: scheduled_tasks.init(bot, register_plugin_jobs: Callable[[BackgroundJobRegistry], None]) calls it with the _ScheduleBackgroundJobRegistry instead of get_plugin_manager().hook.register_background_jobs(...). lifespan builds it from server.plugins.manager (a small function there that fires pm.hook.register_background_jobs). Behaviour is identical: the same hook fires with the same registry at the same point in init. TASK-52 moves the scheduler runtime into server/scheduler/ and can then call the manager directly.
- lifespan.py's PluginManager type comes from server.plugins.manager (a re-typed return of get_plugin_manager), so pluggy is imported nowhere in server/ except server/plugins/.
- Decision text: edit in this PR (AC from the task): plugins.md (line 18 hookspec list loses register_slack_listeners and gains the new locations; Tolerated list drops the two infrastructure/plugins items; the Current-code bullets updated), platform-transports.md:73-74, platform-entrypoints.md:22,66, i18n.md:56, hookspec-deprecation.md (the register_slack_commands example, line 12, and the inventory test path, line 25), transport-slack.md:66, plugin-architecture.md:42 (contracts may import third-party types named by a hookspec parameter, FastAPI and structlog). The stale register_slack_listeners text from TASK-26.1.3 is fixed here because these files are edited anyway for the tolerated lists.

Steps:
1. Create app/server/plugins/__init__.py (docstring), base.py (auto_discover_plugins, moved verbatim) and manager.py (moved; `pluggy.PluginManager(PLUGIN_NAMESPACE)`; adds register_background_jobs(registry) helper).
2. Delete app/infrastructure/plugins/ entirely.
3. server/lifespan.py: imports rewritten; drops `from pluggy import PluginManager`; passes the helper to scheduled_tasks.init via _start_scheduled_tasks (lifespan.py:106-117).
4. jobs/scheduled_tasks.py: init takes the callable; the get_plugin_manager import is removed.
5. Rewrite test imports and patch strings in place; the three scheduled_tasks tests now pass a MagicMock callable instead of patching get_plugin_manager (same assertion that the registration hook fires once).
6. Update the decision records listed above.

Tests first:
- app/tests/unit/server/plugins/test_server_plugins_manager_namespace.py: get_plugin_manager() is cached, its project name is PLUGIN_NAMESPACE and it carries FeatureLifecycleSpecs.
- app/tests/unit/server/plugins/test_server_plugins_pluggy_confinement.py: AST scan of app/ production code finds pluggy imports only in contracts/ and server/plugins/ (tests excluded).
- app/tests/unit/server/plugins/test_server_plugins_register_background_jobs.py: the helper fires the hook with the registry it is given.
- tests/unit/jobs/test_scheduled_tasks.py: init(bot, callable) calls the callable once with a registry (edited in place).
- Existing boot tests (access discovery, i18n hook discovery, hookspec registration) and legacy_surface stay green.

Verify: rg "infrastructure.plugins" app (code and tests) is empty; lint-imports 8 kept with no entry added (contract (a) stays at 11 ignored after 8a); gates; start the app import path via tests/unit/server/test_main.py.
AC map: #1 steps 1-2 + rg; #2 steps 1,3 + confinement test; #3 steps 1 + namespace test; #4 steps 3-5 + jobs tests; #5 step 6 + rg over decisions/ for infrastructure/plugins; #6 gates.
Size: 7 production files (3 new under server/plugins, 3 deleted, lifespan.py, scheduled_tasks.py), about 60 LOC changed of about 200 moved, plus 8 decision-record lines. Two subsystems only in the weak sense (server, jobs signature, docs); the jobs change is 6 lines and forced by layer (a).
Behaviour: none intended; scheduled_tasks.init gains a required parameter, so any caller other than lifespan fails loudly (rg shows lifespan.py:117 is the only one).
Blast radius: startup ordering must be unchanged (get_plugin_manager is lru_cached; i18n phase calls it before registration). Rollback: git revert.
Doubt to verify: nothing under app/bin, Makefile or .github references infrastructure/plugins (rg on 2026-10-01 found only a prose mention in app/bin/check_aws_platform_seam.py:33 naming lifespan, no path).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-01 14:59
---
Plan approved 2026-10-01 (Guillaume Charest, in session), as written. See the TASK-107 approval comment for the decisions confirmed across layers 8a-8d.
---
<!-- COMMENTS:END -->
