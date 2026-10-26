---
id: TASK-112.2
title: >-
  Plugin enablement keys by product area; a disabled plugin is never imported or
  registered
status: In Progress
assignee: []
created_date: '2026-10-23T19:21:00Z'
updated_date: '2026-10-26T14:24:00Z'
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
- [x] #1 base.toml has one [plugins.<area>] table per product-scope area, and every installed entry point has exactly one key; a missing, unknown or duplicated name fails boot naming it (boot tests)
- [x] #2 A plugin disabled in the environment file is never imported or registered: no routes, no OpenAPI entries, no hookimpl calls, no settings reads (boot test)
- [x] #3 An environment that disables every plugin boots; an empty entry-point group still fails boot
- [x] #4 decisions/product-scope.md lists user_rotations under incident response and describes area enablement as a configuration change
- [x] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
- [x] #6 An import-linter protected contract lists every entry-point module, so no host, legacy or sibling code imports a plugin; existing violations are shrink-only ignore entries naming their removing task, and a boot test fails when the list and the entry points differ
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Single PR from an up-to-date main (TASK-111.9 merged as e34b1a27, so base.toml and _validate_slices already carry its changes).

Size: 8 production files plus five empty __init__.py (pyproject.toml added for the import contract), ~170 LOC added, ~15 removed; one subsystem (host plugin loading, its configuration and its import rule). Under the gate.

Decisions (2026-10-26, human review of the first draft)
- Dead code is always deleted: reconcile_access_sync goes in this PR.
- load_plugins takes the disabled names, not the slice: CLAUDE.md settings rule (pass the narrowest slice) and decisions/configuration.md (the host reads the tables as maps).
- The four area fields are required, so a missing area table fails boot: decisions/configuration.md (the base file holds every slice's table; fail fast) and product-scope.md (four areas). TASK-114's generator writes the key into the right area table (AC added there).
- Gap closed: plugins.md said a disabled plugin is never imported, but plugin-architecture.md let server/ (and the legacy api/jobs layer) import anything, and jobs/scheduled_tasks.py did. pluggy 1.7.0 skips ep.load() for a blocked name (verified in load_setuptools_entrypoints), the same way pytest's -p no:<name> blocks before loading (https://docs.pytest.org/en/stable/how-to/plugins.html); Backstage enables and disables backend features from static configuration through feature loaders (https://backstage.io/docs/next/backend-system/architecture/feature-loaders). Blocking only works if nothing else imports the plugin, so an import-linter protected contract (https://import-linter.readthedocs.io/en/latest/contract_types/protected/) lists the entry-point modules. ADRs amended 2026-10-26: plugin-architecture.md (server row, Checks, changelog), plugins.md (Checks, changelog). Scope added: TASK-146.1 (user_rotations deletion removes its key and contract entries), TASK-124.6 (the legacy /geolocate/{ip} route stops importing the plugin), TASK-114 (generator writes the area key and the contract entry).
- Local opt-in: verified that PLUGINS__PLATFORM_ACCESS='{"access.sync": true}' merges into the TOML table key by key; decisions/configuration.md records it. Documenting the AWS profile the access plugins need locally moved to TASK-166 (AC added).

Research findings (call sites)
- app/pyproject.toml:41-50: nine entry points in group sre_bot.
- app/server/plugins/manager.py:45-63 load_plugins: calls pm.load_setuptools_entrypoints, raises no_plugins_loaded when nothing registered. _register_slack_per_plugin (:99) already skips blocked names.
- app/server/lifespan.py:286-288: the only production caller of load_plugins.
- app/server/configuration/host_configuration.py:139-162 _validate_slices, HostConfiguration (:44), constructed only at :152.
- app/jobs/scheduled_tasks.py:20-23 imports packages.access.sync.providers at module level; lifespan imports jobs.scheduled_tasks, so access.sync is imported at boot whatever its key says. Its only user, reconcile_access_sync (:207-213), is never scheduled (init :101-129 does not call it); the plugin schedules its own reconciliation (packages/access/sync/__init__.py:94-106). Dead code: deleted here, otherwise AC #2 cannot hold for access.sync.
- Known cross-plugin imports, not fixed here (every key true), kept as shrink-only ignore entries in the new contract: packages/oncall_sync imports packages.user_rotations (ports.py:16, providers.py:19, __init__.py:19; TASK-146.1 deletes user_rotations, TASK-123 is superseded and the existing contract (f) comment naming it is corrected); app/api/v1/routes/geolocate.py:6 imports packages.geolocate.schemas (legacy route; TASK-124.6).
- Test callers of load_plugins: tests/unit/server/plugins/test_server_plugins_loader_entrypoints.py, tests/integration/infrastructure/hooks/test_i18n_hook_discovery.py:14,32, tests/integration/packages/access/test_access_plugin_discovery_registration.py:63; eight lifespan tests patch server.lifespan.load_plugins (signature-agnostic).
- tests run with ENVIRONMENT=ci (pyproject pytest-env), so base.toml values apply in tests.
- decisions/product-scope.md already lists user_rotations under incident response and describes enablement as a configuration change (amended 2026-10-23): AC #4 is verify-only.

Steps
1. app/config/base.toml: [plugins.incident_response] "incident.comms", "incident.scribe", oncall_sync, user_rotations = true; [plugins.cloud_operations] empty (comment: no plugin yet; legacy modules/aws is not a plugin); [plugins.platform_access] "access.catalog", "access.request", "access.sync" = false (comment: production runs them off today; TASK-112.3 deletes their in-code switches); [plugins.workplace_utilities] geolocate, rant = true. Header comment: one key per entry point, the name as in pyproject.toml. No override in local, ci or production files.
2. app/server/plugins/settings.py (new): PluginsSettings(ConfigurationSlice), toml_table_header ("plugins",), env_prefix PLUGINS__; four required fields incident_response, cloud_operations, platform_access, workplace_utilities: dict[str, bool] (required, so a missing area table fails boot; extra="forbid" fails an unknown area). Method enablement() -> dict[str, bool] merging the areas. Pure function check_plugin_enablement(settings, installed: Iterable[str]) -> None raising ConfigurationError that names: an installed name with no key; a key naming no installed entry point; a name under two areas (names both areas). get_plugins_settings() lru_cache singleton, like server/slack/settings.py.
3. app/server/plugins/manager.py: installed_plugin_names() reads entry-point names of PLUGIN_NAMESPACE from importlib.metadata.distributions() (the same source pluggy iterates, so test fakes cover both) without loading them. load_plugins(pm, disabled: Collection[str], logger): raise when the group has no entry points (message "no entry points in group ..., run uv sync"), call pm.set_blocked(name) for each disabled name, then pm.load_setuptools_entrypoints; log feature_plugins_loaded with plugins=[...] and disabled=[...]. Every plugin disabled boots with plugins=[].
4. app/server/configuration/host_configuration.py: _validate_slices builds get_plugins_settings(), runs check_plugin_enablement(plugins, installed_plugin_names()); HostConfiguration gains disabled_plugins: frozenset[str] (names whose key is false). A failure goes through the existing configuration_invalid CRITICAL path.
5. app/server/lifespan.py:288: load_plugins(pm, configuration.disabled_plugins, ...).
6. app/jobs/scheduled_tasks.py: delete reconcile_access_sync and its packages.access.sync import (dead code, see findings); delete its tests in tests/unit/jobs/test_scheduled_tasks.py.
7. app/pyproject.toml: new import-linter protected contract "(m) A plugin's modules are imported only from inside the plugin", protected_modules = the nine entry-point modules, allowed_importers = [] (as_packages keeps imports inside a plugin legal), unmatched_ignore_imports_alerting = error, ignore_imports: the three oncall_sync -> user_rotations lines (TASK-146.1) and api.v1.routes.geolocate -> packages.geolocate.schemas (TASK-124.6). Contract (f)'s comment: TASK-123 -> TASK-146.1. Verify protected contracts treat as_packages as stated; if lint-imports reports intra-plugin imports, fall back to a forbidden contract with source_modules = server, jobs, api, modules and the other plugins.
7b. Empty __init__.py in app/api/v1, app/api/v1/routes, app/api/routes, app/modules/ops and app/modules/slack. Without them these directories are namespace packages that import-linter does not scan, so no contract saw api.v1.routes.geolocate -> packages.geolocate (found 2026-10-26). Trial on a scratch copy: all 12 existing contracts stay kept and contract (m) reports exactly jobs -> access.sync (deleted in step 6), api.v1.routes.geolocate -> packages.geolocate.schemas and the three oncall_sync -> user_rotations lines. modules/webhooks/patterns stays a namespace: its import-time filesystem walk lists the directory, and the webhooks reassessment (TASK-168, doc-11 rows 21 and 22) deletes the walk and modules/webhooks. mypy and pytest must stay green with the new package markers.
8. Docs: .claude/skills/plugin-registration-lifespan/SKILL.md gains "a new plugin is one entry-point line plus one key in its area's [plugins.<area>] table in base.toml"; decisions/plugins.md changelog line only if wording changes (the 2026-10-23 line already records the decision). No other ADR change expected.

Tests (TDD, failing first)
- tests/unit/server/plugins/test_server_plugins_enablement_check.py: complete keys pass; missing name fails naming it; unknown name fails naming it; name in two areas fails naming name and both areas; enablement() merges areas (happy, failure, boundary).
- tests/unit/server/plugins/test_server_plugins_settings_load.py: PluginsSettings reads the four area tables from tmp files; a missing area table fails; an unknown area table fails (extra forbid); quoted dotted names load as keys.
- tests/unit/server/plugins/test_server_plugins_loader_entrypoints.py (extend; fake dist-info): a disabled entry point's module is never imported (module source raises on import and is absent from sys.modules) and is not registered; every entry point disabled boots with plugins=[]; an empty group still raises; existing tests pass disabled=().
- tests/integration/server/test_server_plugins_enablement_boot.py: the real base.toml against the real installed entry points passes check_plugin_enablement (every entry point has exactly one key); base has access.* false; loading with the ci configuration's disabled names leaves the access modules unregistered and a FastAPI app built through register_routes has no access routes and no access OpenAPI paths.
- tests/integration/server/test_server_lifespan_configuration_phase.py (extend): load_host_configuration over a tmp config dir missing one key fails with configuration_invalid naming the entry point.
- tests/integration/server/test_server_plugins_enablement_boot.py also asserts the protected contract's protected_modules (read from pyproject.toml) equal the installed entry-point modules.
- make check-import-contracts: the new contract is kept; deleting step 6 first makes the jobs -> access import disappear before the contract lands.
- Update load_plugins callers: test_i18n_hook_discovery.py and test_access_plugin_discovery_registration.py pass disabled=() (they assert discovery, not enablement).

AC traceability
- AC #1 -> steps 1, 2, 4 -> enablement_check, settings_load, enablement_boot (real files), configuration_phase.
- AC #2 -> steps 3, 5, 6 -> loader_entrypoints (not imported, not registered, no hookimpl calls; a module that raises on import proves no settings read), enablement_boot (no routes, no OpenAPI).
- AC #3 -> step 3 -> loader_entrypoints (all disabled boots; empty group raises).
- AC #4 -> verify-only, decisions/product-scope.md lines 18-23 and 42.
- AC #5 -> gates.
- AC #6 -> step 7 -> make check-import-contracts, enablement_boot (list equals entry points).

Assumptions and doubts (verify during implementation)
- check-settings-key-ownership accepts a slice whose fields are dict[str, bool] over nested [plugins.<area>] tables (the [slack.tenant] precedent is a nested model): run the check after step 2; if it rejects, adjust the check's table walk, not the slice shape.
- pydantic-settings TomlConfigSettingsSource with deep_merge keeps quoted dotted keys ("access.sync") as single dict keys: covered by settings_load.
- pm.set_blocked before load_setuptools_entrypoints skips ep.load() (pluggy checks is_blocked first): covered by the never-imported test.
- No other boot-time import of packages.access after step 6: rg for "packages.access" and import_module strings outside packages/access and tests.

Blast radius and rollback
- Production: access.catalog, access.request and access.sync stop registering. Their routes (behind the WAF 403, TASK-163) and the /sre access Slack subcommands leave production; access is already switched off there by ACCESS_*_ENABLED, so no working feature is lost. Every other plugin is unchanged.
- A wrong key set fails boot in the configuration phase; the circuit breaker rolls back. One git revert restores the previous behaviour. No secret, SSM or terraform change.
- Local: access plugins no longer load locally (they need a cross-account AWS profile anyway; follow-up gap already noted on row 9.9b).

Post-deploy checks: new phase post-plugins in /workspace/tmp/deploy-checks.zsh: rollout COMPLETED, no configuration_invalid, feature_plugins_loaded lists the six enabled plugins with disabled=[access.catalog, access.request, access.sync], /version and /health, Slack up (socket-mode notice). Manual: /sre help no longer lists access; /incident still works.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26, implemented (In Progress, PR to open).

Changes: config/base.toml gains [plugins.incident_response|cloud_operations|platform_access|workplace_utilities] (access.* false, every other key true; no environment override). server/plugins/settings.py: PluginsSettings (four required area maps), disabled(), check_plugin_enablement (missing, unknown and duplicated names, all reported in one error). server/plugins/manager.py: installed_plugin_names() reads the group from distribution metadata without importing; load_plugins(pm, disabled, logger) blocks each disabled name before load_setuptools_entrypoints, fails only on an empty group (no_plugin_entry_points), logs plugins and disabled. host_configuration.py runs the check in the configuration phase and carries disabled_plugins; lifespan passes them. jobs/scheduled_tasks.py: unscheduled reconcile_access_sync and its access import deleted (dead code). pyproject.toml: import-linter contract (m) protected-plugins over the nine entry-point modules, four shrink-only ignores (oncall_sync -> user_rotations for TASK-146.1, legacy geolocate route for TASK-124.6); contract (f) comment TASK-123 -> TASK-146.1. Empty __init__.py in api/v1, api/v1/routes, api/routes, modules/ops, modules/slack so import-linter scans them. plugin-registration-lifespan skill updated.

Decision taken in implementation: the loader rejected the dotted entry-point keys (lower snake_case rule). It now accepts quoted keys of dot-joined lower snake_case segments; the rule's purpose (no mixed-case key pydantic-settings would ignore) holds, and a dotted key in a field table still fails extra=forbid. Recorded in decisions/configuration.md (Case, changelog 2026-10-26).

Tests: test_server_plugins_enablement_check.py, test_server_plugins_settings_load.py (incl. PLUGINS__PLATFORM_ACCESS merging key by key), loader_entrypoints (a disabled module that raises on import is never imported; all disabled boots; empty group fails), test_server_plugins_enablement_boot.py (real base.toml vs installed entry points; no access routes or OpenAPI paths; contract list equals entry points), configuration phase (missing key fails boot; disabled names reach load_plugins), loader dotted-key tests; lifespan plugin-loading tests now build the configuration before faking distributions and expect only enabled plugins.

Gates (from app/): ruff check All checks passed; ruff format 1039 files already formatted; mypy Found 47 errors in 18 files = baseline, none in touched files; pytest tests --ignore=tests/smoke 5733 passed; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK.

After deploy: zsh /workspace/tmp/deploy-checks.zsh post-plugins (new phase: post-slack-files plus feature_plugins_loaded with six plugins and access disabled). Manual: /sre help no longer lists access; /incident works.
<!-- SECTION:NOTES:END -->
