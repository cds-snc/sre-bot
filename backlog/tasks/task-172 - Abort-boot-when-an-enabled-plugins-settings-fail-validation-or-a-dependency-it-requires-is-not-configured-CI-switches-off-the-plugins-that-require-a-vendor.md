---
id: TASK-172
title: >-
  Abort boot when an enabled plugin's settings fail validation or a dependency
  it requires is not configured; CI switches off the plugins that require a
  vendor
status: To Do
assignee: []
created_date: '2026-10-27T18:10:00Z'
updated_date: '2026-10-29T00:46:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-111.11.2
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
priority: medium
ordinal: 453000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md and lifecycle.md (2026-10-27): an enabled plugin states that it must work in this environment, so every boot failure aborts, in every layer: an import error or a raising hookimpl, a settings slice that fails validation, a vendor slice that fails validation, and a vendor or capability the plugin requires that is not configured. A plugin is switched off with its enablement key, never skipped. Runtime drift (credential checks, TASK-126) never aborts.

TODAY: an invalid feature slice already aborts boot (lifecycle.md Migration listed it as a tolerance of the old skip target; that item is gone). No plugin states a requirement: a plugin enabled without its vendor boots and fails at use. base.toml enables incident.comms, incident.scribe, oncall_sync, user_rotations, geolocate and rant; ci.toml configures no vendor tenant.

SCOPE (ruled 2026-10-29):
- contracts/: one typed error for a required dependency that is not configured, carrying the configuration key; the host logs one CRITICAL plugin_boot_failed event (plugin, phase, error type, key; no secrets) and aborts before yield.
- A new optional, no-argument register_requirements hookspec (decisions/plugins.md hookspec list), fired per plugin before registration: the plugin resolves what it requires and raises the error when it is absent. An import failure is attributed to the entry-point name; the plugin is unknown only when none can be derived.
- This task states one requirement: incident.scribe requires the OpenAI tenant ([openai.tenant], TASK-111.11.2). incident.comms uses text generation optionally (its designed fallback, incident-management.md) and requires none. Slack, Google and Opsgenie requirements (scribe, oncall_sync, rant, user_rotations) are a follow-up through the configured-systems read, with an ADR rule on how CI satisfies them.
- ci.toml switches off incident.scribe only, the one plugin that states a requirement; a guard test fails if a plugin that states a requirement is enabled in ci.toml; pytest-env pins the whole [plugins.incident_response] table (all four keys), as for access.*. A developer switches a plugin off from app/.env.
- feature-packages.md guidance and the TASK-114 generator point new plugins at register_requirements.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An enabled plugin whose settings slice fails validation aborts boot before yield naming the key, in every layer (lifespan test)
- [ ] #2 An enabled plugin whose required vendor is not configured aborts boot with one CRITICAL plugin_boot_failed event naming the plugin and the configuration key, and no secret value (lifespan test)
- [ ] #3 incident.scribe enabled with no [openai.tenant] aborts boot naming openai.tenant; incident.comms enabled with no [openai.tenant] boots and reports text generation unavailable (tests)
- [ ] #4 ci.toml switches off incident.scribe, the only plugin that states a requirement now; the CI boot and the full suite pass with scribe off, and a guard test fails if a plugin that states a requirement is enabled in ci.toml
- [ ] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
IMPLEMENTATION PLAN - PROPOSED, AWAITING HUMAN APPROVAL (2026-10-28)

SIZE GATE VERDICT: passes as ONE PR (about 10 prod files, about 190 prod LOC, 2 subsystems: contracts + server host; config files ci.toml/pyproject are data). Not mechanical-plus-behavior: the per-plugin hook runner replaces the aggregate calls in the same function that now needs attribution (one behavior change). Revert restores the previous behavior. No decomposition needed. If review pushes back, the only natural seam is (a) host abort/attribution + contracts error, (b) scribe requirement + ci.toml, but (b) cannot land first (it needs (a)'s event) and (a) alone is unobservable, so keep one PR.

GROUNDING (current main)
- Entry points: app/pyproject.toml:39-50 (six enabled + three access). Enablement: app/config/base.toml:244-261; ci.toml (app/config/ci.toml) has no [plugins] table; production.toml:37 and local.toml:20 already hold [openai.tenant]; ci has none.
- Host: server/lifespan.py:288 load_plugins (import errors propagate, no event); :191-224 i18n hook + translation init; :298-303 register_feature_integrations; server/plugins/manager.py:63-86 load_plugins, :115-121 register_event_handlers/register_routes/startup_warmup as AGGREGATE pm.hook calls (no plugin attribution), :125-134 per-plugin subset_hook_caller pattern (register_slack_commands), :137-143 register_background_jobs. No try/except anywhere; `rg plugin_boot_failed app` has zero hits.
- Config phase validates every vendor and feature slice before the lifespan: server/configuration/host_configuration.py:166-188 (get_openai_settings :175). It logs configuration_invalid (:154) and raises ConfigurationError (contracts/configuration.py:27).
- Requirements today: none. incident.scribe reads the summarizer only at use (features/incident/scribe/service.py:55,334,975); integrations/openai/summarizer.py:70-72 returns CONFIG_NOT_CONFIGURED. incident.comms: features/incident/comms/adapters/text_generation.py:40-46 (build_status_update_text_generator; tenant None gives UnavailableTextGenerator :22-37), providers.py:21 text_generation_available(); tested by tests/unit/features/incident/comms/test_incident_comms_text_generation_adapter.py:40 and ..._availability.py.
- Vendor reads of the others (all at USE, none at registration): oncall_sync packages/oncall_sync/adapters/slack.py:140 get_slack_settings().user_token (its warmup, __init__.py:46-60, reads only schedules/rotations); rant packages/rant/adapters/slack.py:46 get_slack_web_client; user_rotations none; geolocate packages/geolocate/service.py:42 get_maxmind_client (optional per base.toml:166-168; integrations/maxmind/client.py:160-163 runs unconfigured). ConfiguredSystems (contracts/workplace/configured_systems.py:15) is registry-built in server/services.py:53-60 and covers Slack and Google only; OpenAI is not a WorkplaceSystem.
- Tests: most lifespan tests patch server.lifespan.load_plugins (test_lifespan_core_services.py:42, test_lifespan_vendor_slice_validation.py:113 and 7 more), so they never load these plugins. Real loads: tests/integration/server/test_lifespan_plugin_loading.py:68 (asserts enabled vs ci files; hookimpl-raises test at :91), test_server_plugins_enablement_boot.py:56-65, test_server_lifespan_configuration_phase.py:151 (asserts disabled == access three; WILL change when ci.toml switches scribe off), test_i18n_hook_discovery.py:14. pytest-env pins: app/pyproject.toml:131 (PLUGINS__PLATFORM_ACCESS), :134 (SCHEDULER__ENABLED), :158 (OPENAI__API_KEY blank), ENVIRONMENT=ci.

DESIGN (follows decisions/plugins.md "A plugin states what it requires by resolving it")
1. contracts: `RequiredDependencyError(Exception)` in new app/contracts/plugins/requirements.py, fields `key: str` (e.g. "openai.tenant") and message; no value fields (no secrets). Frozen-dataclass-free: plain exception.
2. New optional hookspec `register_requirements()` (no args) in contracts/plugins/hookspecs.py: a plugin resolves what it needs and raises RequiredDependencyError. Fired per plugin by the host before i18n/registration. (Rationale: existing hooks are gated on Slack provider presence (manager.py:125) or fire too late (startup_warmup); a dedicated hook states the requirement in one place per plugin. See Q1.)
3. Host: new server/plugins/boot.py (or in manager.py): `run_hook_per_plugin(pm, hook_name, phase, logger, **kwargs)` iterating `pm.list_name_plugin()` with subset_hook_caller (the existing pattern, manager.py:125-134), catching Exception, logging ONE CRITICAL `plugin_boot_failed` (plugin, phase, error_type, key; key from RequiredDependencyError.key, or from a pydantic ValidationError/ConfigurationError via the existing describe/loc helper in server/configuration; never the error text when it can carry input values) and re-raising. Used for register_requirements, register_event_handlers, register_routes, startup_warmup, register_slack_commands (replaces the aggregate calls at manager.py:115,118,121 and the loop at :125-134). `load_plugins` import failure: wrap pm.load_setuptools_entrypoints, log plugin_boot_failed with phase plugin_loading (plugin name from the exception's ModuleNotFoundError target when pluggy does not give one: plugin="unknown" is acceptable, see Q4). register_i18n_resources collection (lifespan.py:192) uses the same runner.
4. lifespan.py: call `fire_register_requirements(pm, logger)` right after load_plugins (:288), before i18n. No other lifespan change.
5. incident.scribe requirement: features/incident/scribe/__init__.py gains `@hookimpl register_requirements()` calling `require_openai_tenant()` in a new features/incident/scribe/requirements.py that reads get_openai_settings().tenant (same import comms already uses at adapters/text_generation.py:43) and raises RequiredDependencyError(key="openai.tenant"). incident.comms gets NO hookimpl; its fallback stays.
6. ci.toml: add `[plugins.incident_response]` with `"incident.scribe" = false` and a comment (requires [openai.tenant], which ci has none). Env-file override of one key must keep other keys (verify, Q5).
7. pytest-env pin: add `PLUGINS__INCIDENT_RESPONSE={{"incident.comms": true, "incident.scribe": false, "oncall_sync": true, "user_rotations": true}}` beside the access pin (pyproject.toml:131) with a comment, so a developer's app/.env switching scribe on cannot abort every test boot. Tests that need scribe enable it with monkeypatch + fake tenant. No new run switch otherwise.
8. Docs: decisions/feature-packages.md gets one paragraph (new plugins state requirements via register_requirements; link plugins.md); TASK-114 gets `--comment`/plan note so the generator template includes the hook (generator not built yet: I do not edit it). decisions/plugins.md "Migration/Today" line 85 ("no plugin states what it requires yet") is removed; observability.md already describes plugin_boot_failed.

STEPS (TDD order; red first)
S1 tests (below) red. S2 contracts error + hookspec. S3 runner + event + load_plugins wrap. S4 manager/lifespan wiring. S5 scribe hookimpl. S6 ci.toml + pyproject pin. S7 docs. S8 gates: ruff, mypy, pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
Enabling for the contracts import-linter (pyproject.toml:231+): contracts must not import server; scribe imports only contracts + integrations.openai.settings like comms.

TEST MATRIX (files in app/tests, test_<domain>_<entity>_<action>.py)
- tests/integration/server/test_lifespan_plugin_boot_failure.py (AC1, AC2; real PluginManager, write_plugin_dist fixture as test_lifespan_plugin_loading.py:55-100):
  * plugin whose register_requirements raises RequiredDependencyError("openai.tenant") aborts before yield; exactly one CRITICAL plugin_boot_failed with plugin, phase, error_type, key; no secret in captured logs (set OPENAI__API_KEY=sk-test-secret and assert absent).
  * plugin whose startup_warmup reads a settings slice that fails pydantic validation aborts before yield, event names the key (AC1; also one case each for register_routes and a hookimpl that raises generally: phase differs, key absent).
  * import failure logs plugin_boot_failed phase plugin_loading and re-raises ModuleNotFoundError.
  * disabled plugin with a failing requirement is never imported and boots (boundary).
  * enabled plugin without register_requirements boots (optional hook).
- tests/unit/server/plugins/test_server_plugins_hook_runner.py: runner attributes the right plugin when two are registered; second plugin not called after first raises; non-failing path calls every plugin once with kwargs.
- tests/unit/contracts/plugins/test_contracts_plugins_required_dependency_error.py: carries key, str() names key, no value.
- tests/unit/features/incident/scribe/test_incident_scribe_requirements_resolve.py (AC3): no tenant raises RequiredDependencyError key "openai.tenant"; tenant present passes (patch get_openai_settings as comms tests do).
- tests/integration/server/test_lifespan_incident_plugins_openai_requirement.py (AC3, real entry points, scribe+comms enabled): no [openai.tenant] aborts naming openai.tenant; with scribe switched off and comms on it boots and text_generation_available() is False (reuses comms providers.py:21 with cache_clear).
- tests/integration/server/test_server_plugins_enablement_boot.py (existing, adjust) and test_server_lifespan_configuration_phase.py:151 (existing, adjust expected disabled set to access three + incident.scribe) and test_lifespan_plugin_loading.py:68 (adjust) (AC4).
- tests/integration/server/test_server_ci_boot_without_vendor_tenant.py (AC4): load ci files with the pytest-env pins, real entry points, patched Slack/core services as _stub_startup does; boot reaches yield with no vendor tenant configured; plus a guard that every plugin whose register_requirements exists is disabled in ci.toml (reads pm hook impls + ci file, so a future requirement without a ci switch-off fails here).
- AC5 gates run as listed. Full suite proves AC4 end to end.

AC TRACEABILITY
#1 -> S3,S4; test_lifespan_plugin_boot_failure (settings-slice cases). #2 -> S2,S3; test_lifespan_plugin_boot_failure (requirement + no-secret). #3 -> S5; scribe requirements unit + openai-requirement integration. #4 -> S6; ci boot test + full suite + adjusted enablement tests. #5 -> S8. Enabling work: S7 (docs, from SCOPE last bullet).

ASSUMPTIONS TO VERIFY
- pytest-env env value for a table replaces/merges as the access pin does (pyproject.toml:131): verify by test that comms/oncall_sync/user_rotations stay enabled with the pin; Q5.
- pluggy raises original exceptions from subset_hook_caller calls (no wrapping): verify in the runner unit test.
- the description claim that "settings fails" is already abort-by-propagation: confirmed (no catch in manager/lifespan); the plan only adds the event and the key.
- disabled plugins appear in pm.list_name_plugin() with plugin None (manager.py:122 docstring); the runner skips them.
- ValidationError to key mapping: reuse the describe_validation_error helper used by host_configuration.py:150-153; locate its exact module in S3 (rg found no direct definition via name search in server/configuration; if it lives elsewhere, import it, else add a small `key_of(error)` in the runner).

BLAST RADIUS AND ROLLBACK
Merging to main deploys. Risk: production boot aborts if scribe is enabled and [openai.tenant] is missing. production.toml:37 has it and OPENAI__API_KEY is already a task-definition secret (TASK-111.4, completed), and the config phase already fails boot on a tenant with a missing key, so no new prod failure is expected. Ordering: none (no prerequisite env/terraform). Rollback: a single revert restores service; ECS circuit breaker also rolls back a failing boot. The per-plugin runner changes call order of aggregate hooks to per-plugin: pluggy ordering across plugins stays LIFO-registration vs sorted list order; no hook relies on cross-plugin order (verify by rg in S4).

HUMAN STEPS
Review plan; confirm Q1-Q5; after merge, watch the first deploy's task start (bin/deploy-checks.zsh post, human-run); optionally set app/.env PLUGINS__INCIDENT_RESPONSE to switch scribe on locally (local.toml has [openai.tenant]).

OPEN QUESTIONS (recommendation each)
Q1 Where does a plugin state requirements? Options: reuse register_slack_commands, or a new hookspec. Recommend the new no-arg `register_requirements` hookspec (explicit, always fired, attributable). This is a contracts API addition: needs your approval.
Q2 Scope of "requires a vendor". Only scribe has a ruled requirement (OpenAI). Scribe also uses Slack and Google Docs; oncall_sync, rant, user_rotations use Slack at use time; geolocate's MaxMind is optional. Recommend this PR states OpenAI for scribe only and ci.toml switches off only incident.scribe; create a follow-up task for Slack/Google/Opsgenie requirements (via ConfiguredSystems, needs a rule for what the CI env, which has no Slack tenant, does with rant/oncall_sync/user_rotations) rather than switching six plugins off in CI and losing their coverage. Note the task text implies all six; AC4 reads "every plugin that requires a vendor" so the AC is satisfied under this scope.
Q3 TASK-145.7 AC #9 (new-incident policy): resolves in its own plugin via the same hook; out of scope here, enabled by it.
Q4 Import-failure attribution: pluggy gives no plugin name on ImportError. Recommend plugin = entry-point name derived by iterating installed_plugin_names() (manager.py:46) and the failing module, falling back to "unknown"; acceptable for this PR.
Q5 pytest-env pin for scribe: pin the whole [plugins.incident_response] table (mirrors the access pin) vs rely on ci.toml. Recommend the pin per standing decision; if env table overrides replace rather than merge, list all four keys (as planned).
Q6 TASK-126 title/file name still says "on_boot_failure abort|continue" while its body is credential checks; recommend renaming the file title via CLI later to avoid contradicting the no-override ruling (not this PR).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- 2026-10-29 (delivery session; human asked for each open question to be assessed against the ADRs and doc-11): Q1 new register_requirements hookspec: plugins.md rules the requirement but names no hook (gap); Backstage (explicit plugin dependency declaration, startup fails on an unresolved one: https://backstage.io/docs/backend-system/architecture/backends) and Django system checks (registered at app load, an error blocks startup: https://docs.djangoproject.com/en/6.0/topics/checks/) support a dedicated explicit hook; plugins.md gains it in the hookspec list, a Changes line and Sources. Q2 only scribe's OpenAI requirement now: no ADR rules how CI satisfies Slack/Google/Opsgenie requirements (switching six plugins off in CI loses their tests), so that rule and those requirements are a follow-up after TASK-145.5.9's read (proposed, not created); plugins.md Tolerated lists it. Q3 tightened: entry-point name (enablement already keys every installed entry point), unknown only as a last resort (plugins.md requires the event to name the plugin). Q4 pin all four keys of [plugins.incident_response]; the guard test and a test that comms, oncall_sync and user_rotations stay enabled with the pin stay in the plan. Q5 TASK-126 retitled separately (comment there), not in this PR. Also fixes plugins.md's stale Boot test line (a feature with an invalid slice aborts, not absent). ACs #3 and #4 and the description reworded. Applied, pending plan approval.

- 2026-10-29: plan approved (human), with the 2026-10-29 rulings above.

2026-10-29: the Slack, Google and Opsgenie requirements follow-up is TASK-175 (created, human 2026-10-29).
<!-- SECTION:NOTES:END -->
