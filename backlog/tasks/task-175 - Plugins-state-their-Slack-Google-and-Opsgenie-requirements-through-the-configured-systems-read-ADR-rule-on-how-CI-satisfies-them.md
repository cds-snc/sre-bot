---
id: TASK-175
title: >-
  Plugins declare their Slack, Google, Opsgenie and user-token requirements; CI
  checks the production and local configuration against them
status: In Progress
assignee: []
created_date: '2026-10-29T00:46:00Z'
updated_date: '2026-10-29T19:09:00Z'
labels:
  - plugins
dependencies:
  - TASK-172
  - TASK-145.5.9
priority: medium
ordinal: 459000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-172 (human, 2026-10-29: create; decisions applied 2026-10-29). Plugins state their vendor requirements as DECLARATIONS: register_requirements returns Requirement values (a setting path such as slack.tenant, google_workspace.tenant, opsgenie.tenant, openai.tenant, slack.user_token) and the host resolves them against the configured-systems read (workplace systems) and the cached settings slices (other vendors and secret fields), collects every failure across plugins, logs one CRITICAL plugin_boot_failed per failure naming the setting, then aborts boot. incident.scribe (reshaped from TASK-172), oncall_sync (slack.tenant, slack.user_token, opsgenie.tenant), rant and user_rotations (slack.tenant) declare theirs. decisions/plugins.md records the declarative rule and a two-part CI rule: a production and local configuration check in the existing pytest job (every declared requirement of every plugin the file enables resolves, and every required env-only secret is supplied by terraform/ssm.tf or a Codespace secret), and ci.toml switching the requiring plugins off for the runtime test boot with a guard test. Closes the plugins.md Tolerated entry. Separate from TASK-164's CI env-name audit (no overlap). local.toml switches oncall_sync off because no Codespace secret holds SLACK__USER_TOKEN.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 decisions/plugins.md records the declarative requirement rule and the two-part CI rule (production and local configuration check; ci.toml switch-off with a guard test), with sources, and drops the Tolerated entry once this task lands
- [x] #2 register_requirements returns Requirement declarations; incident.scribe (openai.tenant, slack.tenant, google_workspace.tenant), oncall_sync (slack.tenant, slack.user_token, opsgenie.tenant), rant and user_rotations (slack.tenant) each declare theirs, with no vendor code in the plugins
- [x] #3 The host resolves declarations against the configured-systems read and the cached slices, collects every unmet requirement across enabled plugins, logs one CRITICAL plugin_boot_failed per failure with plugin and setting, then aborts boot; tests cover each plugin's success and failure
- [x] #4 A pytest test loads production.toml and local.toml, collects the declared requirements of every enabled plugin and fails when one does not resolve or a required env-only secret is not supplied (terraform/ssm.tf for production, a Codespace secret for local); ci.toml switches the requiring plugins off with a guard test; local.toml (oncall_sync off) still boots in development
- [x] #5 Ride-along (human, 2026-10-29): CLAUDE.md Verification, the python-quality-gates and tdd-implementation skills and .github/agents/implementation.agent.md state the gate cadence (ruff and targeted tests during implementation; full mypy then fixes, then full pytest alone, once each at the end; rerun only on a real error; never in parallel), and CLAUDE.md's size gate exempts deletion-only PRs; edited in the working tree 2026-10-29, shipped in this task's PR
- [ ] #6 SLACK__USER_TOKEN is declared env_only with source codespaces; app/.env.example regenerated; local.toml keeps oncall_sync on; the local configuration check passes with the Codespaces secret source; make env-checks run by the human after merge shows the Codespaces secret present
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v2 (rewritten 2026-10-29 to apply the human's decisions; task-planner; proposed, awaiting approval). Replaces the earlier plan in full.

Decisions applied (human, 2026-10-29)
1. Requirements are DECLARATIVE: register_requirements returns declarations; the host resolves them, collects every failure across plugins, logs one CRITICAL plugin_boot_failed per failure, then aborts. No new hookspec argument, no Opsgenie adapter, no WorkplaceSystem change.
2. user_rotations requires slack.tenant. oncall_sync requires slack.tenant, opsgenie.tenant and slack.user_token.
3. CI rule in two parts: (a) a production/local configuration check in the existing pytest job; (b) ci.toml switches the requiring plugins off for the runtime test boot, with TASK-172's guard test.

Verified facts
- Hookspec contracts/plugins/hookspecs.py:50 returns None and takes no argument; typed error contracts/plugins/requirements.py; per-plugin runner server/plugins/boot.py call_hook_per_plugin (subset_hook_caller per plugin, so attribution is kept; pluggy returns one list of non-None impl results per call, one impl per plugin, so the runner flattens it) and log_plugin_boot_failed; lifespan.py:257 resolves requirements after load_plugins and before registration. TASK-156 summary is logged after registration, so a failure aborts before any configuration_slice event (unchanged).
- Resolution sources: workplace systems (slack.tenant, google_workspace.tenant) through ConfiguredSystems (core service, built in lifespan phase 2, before plugin loading); other vendors and secret fields through the cached slices (get_openai_settings, get_opsgenie_settings, get_slack_settings; SecretStr, empty = unset). Slice getters are lru-cached and host-validated, so they are cheap and attribute nothing to a plugin.
- SLACK__USER_TOKEN: env_only(..., "local") in integrations/slack/settings.py:72; it is in terraform/ssm.tf sre_bot_secret_names (so production has it) but source "local" means NO Codespace secret holds it. SLACK__BOT_TOKEN is "codespaces". local.toml configures [opsgenie.tenant] (key is a Codespaces secret) and [slack.tenant]; Google is "codespaces".
- Env-only declarations are already machine-readable: app/bin/generate_env_example.py collect() returns EnvName(name, module, source, description) derived from env_only(); app/bin/audit_env_coverage.py terraform_parameters() parses terraform/ssm.tf. app tests already import bin.* (tests/unit/bin/test_bin_audit_env_names_*.py) and bin is not an import-linter root package, so the check may import both with no import-contract change and no parser move.

Design
- contracts/plugins/requirements.py: add `@dataclass(frozen=True) class Requirement: setting: str` (dotted path "<table>.<field>", e.g. "slack.tenant", "slack.user_token", "opsgenie.tenant", "openai.tenant"). Setting path only, not a workplace system plus setting: plugins stay vendor-free (no WorkplaceSystem or enum import), and the host owns which paths are workplace systems (a small mapping slack.tenant->SLACK, google_workspace.tenant->GOOGLE). Frozen dataclass per type-model-boundaries: an internal canonical value, not an untrusted I/O boundary. RequiredDependencyError is kept as the host's per-failure value (field setting) or replaced by a RequirementFailure dataclass; decide in implementation, keep the `setting` log field.
- Hookspec: register_requirements(self) -> Sequence[Requirement] (still no argument; widening the return from None is additive for scribe's impl, which is reshaped to return (Requirement("openai.tenant"),)). Inventory test updated.
- Host resolver (server/plugins/requirements.py or manager.py): for each plugin in boot order call the hook, flatten, resolve each Requirement (workplace path -> configured-systems tenants; else getattr path on the cached slice, None/empty SecretStr = unmet), collect ALL failures across ALL plugins, log one CRITICAL plugin_boot_failed per failure (plugin, phase, setting; never `key`), then raise one aggregate error. A hookimpl that itself raises is still logged and re-raised as today.
- Plugin statements: scribe: openai.tenant (existing), slack.tenant, google_workspace.tenant; rant: slack.tenant; user_rotations: slack.tenant; oncall_sync: slack.tenant, slack.user_token, opsgenie.tenant. The scribe adapters/requirements.py and its get_openai_settings import are deleted (dead after the reshape).

CI rule (to record in plugins.md)
a. Configuration check in the existing pytest job: app/tests/integration/server/test_server_plugins_configuration_requirements.py (name per testing-standards). For ENVIRONMENT=production and a second case local: monkeypatch.setenv ENVIRONMENT; delenv the pytest-env pins PLUGINS__INCIDENT_RESPONSE, PLUGINS__PLATFORM_ACCESS, PLUGINS__WORKPLACE_UTILITIES (if pinned) and SCHEDULER__ENABLED; do not load app/.env; clear the loader/slice caches. Load the real files through the host loader, take the enabled set, load the entry points on a real manager with the disabled names blocked (the existing pm.set_blocked path, no registration hook fired, so no side effects), call only register_requirements, and resolve. Fails if any declared requirement does not resolve, or if a required env_only secret is not supplied: production -> its name is in terraform_parameters(); local -> its EnvName.source is "codespaces" (a "local" source means no Codespace secret holds it). Secret placeholders exist only inside the test, derived from collect() env_only declarations (never a hand list, never in files). Limit, stated in the ADR: it cannot see a wrong or missing value in SSM; boot fail-fast and the ECS circuit breaker still cover that.
b. ci.toml switches off every plugin that declares a requirement (scribe, oncall_sync, user_rotations, rant) for the runtime test boot; TASK-172's guard test (test_server_plugins_ci_requirements_guard.py) now asserts all four, using the declarations. pytest-env pins updated (oncall_sync/user_rotations false in PLUGINS__INCIDENT_RESPONSE; new PLUGINS__WORKPLACE_UTILITIES with rant false).
c. Local: development without a vendor whose credentials no Codespace secret holds boots: local.toml sets oncall_sync = false (slack.user_token is source "local"); a developer who keeps SLACK__USER_TOKEN in app/.env switches it on with PLUGINS__INCIDENT_RESPONSE in app/.env. scribe, rant, user_rotations stay on locally (slack, google and openai are Codespace secrets; google already required by TASK-173).
d. Relation to TASK-164 (row Z, TASK-177 folded in): that task runs the env-name audit (audit_env_names/audit_env_coverage) in CI as a workflow; this check is separate (app pytest, configuration semantics: enabled plugins and declared requirements). No overlap; scope line to be added in both tasks. Relation to TASK-173: unchanged (configuration-phase rule for the legacy handlers, deleted by TASK-145.13).

Steps
1. decisions/plugins.md amendment (proposed text in the hand-off; applied by the human/architecture agent). [AC1]
2. contracts: Requirement; hookspec return type; inventory test. [AC2]
3. server: resolver collecting all failures, runner flattening; lifespan call. [AC3]
4. Hookimpls for the four plugins; delete scribe's adapter. [AC2]
5. config: ci.toml, local.toml (oncall_sync false), pyproject pytest-env pins. No new env names, so no manual-check rule. [AC4]
6. Configuration check test + guard test update. [AC4]
7. AC5 doc ride-along is already in the working tree: not redone.

Tests (success and failure per plugin)
tests/unit/contracts/plugins/test_contracts_plugins_requirement_declare.py; tests/unit/{features/incident/scribe,packages/rant,packages/user_rotations,packages/oncall_sync}/test_*_requirements_declare.py (returns the exact declarations); tests/unit/server/plugins/test_server_plugins_requirements_resolve.py (workplace path via read, slice path, SecretStr empty = unmet, all failures collected across plugins, one critical per failure with setting field, attribution kept, disabled plugin not asked); tests/integration/server/test_lifespan_plugin_requirements_abort.py (real lifespan: two plugins unmet -> two events, no yield; met -> yield); the configuration-check test (production and local) with a negative case (a stubbed terraform set missing SLACK__USER_TOKEN fails); guard test; test_lifespan_plugin_loading.py updated; test_contracts_hookspecs_inventory.py.

Size: ~170 production LOC (resolver ~60, contract ~15, four hookimpls ~25, scribe reshape and deletion -10, config ~12, check test is tests), production files ~13 (hookspecs, requirements, resolver, manager/boot, lifespan, 4 plugin __init__, scribe adapter delete, ci.toml, local.toml, pyproject.toml) plus plugins.md plus 5 AC5 docs. One subsystem (plugins and its configuration). Gate: over ~10 files only by small edits; size exception requested, one PR: the contract, resolver and declarations only compile together, and the ADR plus the check must land with them.

Blast radius and rollback
Merge to main deploys; production enables all four plugins. Boot aborts only if a declared requirement is unmet in production: slack.tenant and opsgenie.tenant are in production.toml; SLACK__USER_TOKEN, OPSGENIE__INTEGRATIONS_KEY, SLACK__BOT_TOKEN and the Google tenant are SSM names (ssm.tf) and #1810 already needs the Google tenant. The new configuration check proves the names and the files before merge; it cannot prove SSM values, so the human confirms before merge (read-only) that the running revision logged configured_systems_built with slack and google and that /sre-bot/SLACK__USER_TOKEN holds a value. A wrong requirement aborts the ECS deploy; the circuit breaker rolls back and git revert restores service. Safe order: #1810 deployed healthy, then this PR; no terraform, IAM or env-name change.

Gate rule for verification
During implementation run ruff and targeted test files only; at the end run full mypy then fixes, then full pytest alone, once each, never in parallel, rerunning only on a real error; plus make check-import-contracts and make check-settings-key-ownership. @contextmanager helpers return Generator[...].

Assumptions to verify
- pluggy returns one flattened result list per subset call (verify in the hook-runner test).
- Dev with SLACK__USER_TOKEN blank still passes slice validation (it does: the token is optional on the slice).
- Loading entry points for the check with disabled names blocked imports no side-effecting module (protected import-linter contract already ensures disabled plugins are not imported).

## Approved 2026-10-29 (human), with these amendments (they override the steps above where they differ)
- Failure type (OQ1): a host-internal frozen dataclass RequirementFailure(plugin, setting) per unmet requirement; the host logs one CRITICAL plugin_boot_failed per failure, then raises one aggregate error. Plugins only return Requirement values. RequiredDependencyError is deleted if nothing else reads it (dead code).
- User token (OQ2): SLACK__USER_TOKEN becomes Codespace-sourced: integrations/slack/settings.py user_token env_only source "local" -> "codespaces"; regenerate app/.env.example (make env-example; the drift test checks it). local.toml does NOT switch oncall_sync off; the local configuration check then requires the Codespaces secret source. Step 5 changes accordingly: an env name's source changes, so this task is under the manual-check rule for make env-checks only (no terraform, task definition, IAM or SSM change: no deploy-checks). Human step before merge: create the Codespaces secret SLACK__USER_TOKEN with a dev-workspace user token (usergroups scopes only; never the production token); after merge: make env-checks and the agent reads tmp/env-checks/.
- Title renamed; ci.toml still switches all four requiring plugins off for the runtime test boot.
- Gates: during implementation ruff and targeted tests only; at the end full mypy then fixes, then full pytest alone, once each, never in parallel; rerun only on a real error; plus make check-import-contracts and make check-settings-key-ownership.
- Scope line for TASK-164 (row Z): its CI env-name audit is separate from this task's configuration check (app tests, configuration semantics); add the same line to TASK-164.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29: plan approved (human) with amendments (see plan, Approved section): RequirementFailure dataclass with one aggregate error; SLACK__USER_TOKEN becomes a Codespaces secret (only oncall_sync reads it today, packages/oncall_sync/adapters/slack.py:140-145; user-list features need it in development); title renamed. Under the manual-check rule for make env-checks only.

2026-10-29: human created the Codespaces secret SLACK__USER_TOKEN (dev workspace); implementation started.

2026-10-29 implementation: Requirement frozen dataclass (contracts/plugins/requirements.py); hookspec returns Sequence[Requirement]; host resolver server/plugins/requirements.py (RequirementFailure, PluginRequirementsUnmetError, one CRITICAL plugin_boot_failed per failure with plugin and setting); call_hook_per_plugin now returns per-plugin results; RequiredDependencyError and scribe's adapter deleted. Declarations on scribe, oncall_sync, rant, user_rotations. SLACK__USER_TOKEN source is codespaces; .env.example regenerated. ci.toml and pytest-env pins switch the four plugins off. Configuration check: tests/integration/server/test_server_plugins_configuration_requirements.py (production and local, with negative cases). Lifespan reads ConfiguredSystems with read_configured_systems() directly because the lifespan tests stub the core services; the registry instance is the same read over cached slices. Two existing configuration-phase tests adjusted for the new pins. AC6 left unchecked: make env-checks after merge is a human step. Gates: ruff clean; mypy reports 41 errors in 14 untouched files (modules/, infrastructure/i18n, features/incident scheduling and meet, integrations/slack/channels.py), none in changed files; full pytest 5960 passed; make check-import-contracts 13 kept 0 broken; check-settings-key-ownership OK.

2026-10-29 (review): configured_systems_built moved from read_configured_systems to the core-service build (server/services.py), so the second read the lifespan makes for requirement resolution adds no boot event (one event per boot, as bin/deploy-checks.zsh expects); tests updated. Gates after the fix: ruff All checks passed; mypy on the changed server and contracts files Success (13 files); full pytest 5961 passed, 44 warnings in 164.93s; check-import-contracts 13 kept, 0 broken; check-settings-key-ownership OK. Full mypy reports 41 errors in 14 files none of this diff touches (modules/*, infrastructure/i18n/service.py and resolvers.py, features/incident/scheduling/adapters/google_calendar.py, features/incident/meet/adapters/google_meet.py, integrations/slack/channels.py); pre-existing, CI runs no mypy, not fixed here. AC #6 waits on make env-checks after merge (human).
<!-- SECTION:NOTES:END -->
