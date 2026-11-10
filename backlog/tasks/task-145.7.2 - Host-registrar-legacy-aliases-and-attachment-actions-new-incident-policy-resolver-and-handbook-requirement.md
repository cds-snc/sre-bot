---
id: TASK-145.7.2
title: >-
  Host registrar legacy aliases and attachment actions; new-incident policy
  resolver and handbook requirement
status: Done
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T19:43:00Z'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/transport-slack.md
  - decisions/incident-management.md
  - decisions/plugins.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 499000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L1, side PR from main (approved program in TASK-145.7's plan, section 2; outline in the parent plan). The Slack registrar gains register_attachment_action and legacy-id aliases for block and attachment actions (prefix enforced on the primary id only; aliases unique, logged, listed for TASK-145.13). incident.response resolves [incident_core] new_incident_system at startup against the configured-systems read and requires [incident_response] handbook_id; production.toml sets new_incident_system = "google" (production configures Slack and Google, so unset would fail boot). transport-slack.md and incident-management.md System selection amended in the same PR. Full plan: TASK-145.7 plan section 5.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 register_attachment_action and legacy aliases on block and attachment actions exist in contracts/slack/registrar.py, server/plugins/slack_registrar.py and integrations/slack/provider.py; a duplicate id across kinds aborts boot; an interactive_message payload with a legacy callback id reaches its listener through Bolt dispatch (tested)
- [x] #2 resolve_new_incident_system covers set+configured, unset+one, unset+several (fails), named-but-unconfigured (fails) and none (fails), and boot logs one CRITICAL plugin_boot_failed naming incident_core.new_incident_system (tested)
- [x] #3 incident.response requires incident_response.handbook_id at registration; production.toml sets new_incident_system = "google" and a configuration test loads it
- [x] #4 decisions/transport-slack.md (aliases) and decisions/incident-management.md (System selection: production sets the policy) amended with dated Changes lines; checks parent ACs #9, #10 and the alias part of #11
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #6 decisions/plugins.md amended: startup_warmup receives the configured-systems read; a plugin names the setting at fault by raising SettingError, which plugin_boot_failed logs in its setting field (tested); dated Changes line
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human) with the Stack L program (TASK-145.7 plan). AMENDED and APPROVED 2026-11-10 (human): program-scope assessment of the boot-policy hook (see the 2026-11-10 comment); extended in place with a size exception.
L1 in full: host prerequisites (side PR from main 8b8d1aeb, branch task-145.7.2-host-prerequisites).
SIZE EXCEPTION (approved 2026-11-10): ~330 production LOC, ~11 code files + 3 ADRs, three subsystems (host Slack transport; plugin host boot; incident response boot). The plugin-host part is ~25 LOC in 4 files and only exists to serve step 6; splitting it out would leave an unused hook argument.
1. app/contracts/slack/registrar.py: register_attachment_action(callback_id, listener, *, legacy_callback_ids: Sequence[str] = ()) and a legacy_action_ids keyword on register_block_action (same semantics); docstrings name decisions/transport-slack.md:39.
2. app/server/plugins/slack_registrar.py: the plugin-prefix check (81-83) applies to the primary id only; legacy ids are exempt, must be non-blank and unique, and are logged once at registration (event slack_legacy_id_registered, fields plugin, legacy_id, id).
3. app/integrations/slack/provider.py: _attachment_actions store beside _block_actions (223); register_attachment_action; aliases stored as extra keys of the same listener; a duplicate id (alias or primary) across block actions and attachment actions aborts boot as _register_listener (636) does; view submissions keep their own namespace (test_same_id_may_name_an_action_and_a_view stays); _attach_interaction_listeners (653) attaches app.attachment_action(id) per key; a read-only legacy_ids() listing for TASK-145.13. The RecordingBoltApp test fake gains attachment_action.
4. decisions/transport-slack.md: the alias mechanism (block and attachment actions), legacy ids exempt from the prefix, listed for the contract task; Changes line.
5. app/features/incident/core/api.py: resolve_new_incident_system(policy: WorkplaceSystem | None, configured: ConfiguredSystems) -> WorkplaceSystem, pure, raising SettingError(setting="incident_core.new_incident_system"). Not in build_incident_store (TASK-145.5.5: the store builder stays policy-free; a test asserts it).
5a. (amendment) app/contracts/configuration.py: SettingError(ConfigurationError) carrying setting: str (the dotted table.key). app/server/plugins/boot.py: _setting_at_fault gains a SettingError case returning its setting, so plugin_boot_failed names it (plugins.md:109).
5b. (amendment) app/contracts/plugins/hookspecs.py: startup_warmup(logger, systems: ConfiguredSystems); existing hookimpls that accept only logger keep working (pluggy opt-in arguments). app/server/plugins/manager.py register_feature_integrations and app/server/lifespan.py pass the configured-systems read the host already builds for requirement resolution (lifespan.py:252), read once.
6. app/features/incident/response/plugin.py: register_requirements adds Requirement("incident_response.handbook_id") (TASK-184 built slice; INCIDENT_RESPONSE__HANDBOOK_ID is in terraform/ssm.tf, so the production configuration test holds); a startup_warmup(logger, systems) hookimpl resolves the policy from get_incident_core_settings().new_incident_system, so a failure aborts boot with one CRITICAL plugin_boot_failed (phase startup_warmup, setting incident_core.new_incident_system).
7. app/config/production.toml: [incident_core] new_incident_system = "google"; local.toml the same (local configures Slack and Google: the Google tenant comes from Codespaces secrets and incident.response is enabled, so unset would fail local boot); ci.toml keeps the plugin off (TASK-175). decisions/incident-management.md System selection: the response plugin's startup_warmup resolves it; unset resolves to the only configured system; production sets the policy explicitly; Changes line. decisions/plugins.md: startup_warmup receives the configured-systems read; a plugin names the setting at fault by raising SettingError; Changes line.
Tests (strict zone): tests/unit/server/plugins/test_server_slack_registrar_legacy_ids.py (alias registered and listed, prefix refused on primary only, duplicate across block/attachment kinds aborts boot, blank alias refused); tests/unit/integrations/slack/test_slack_provider_attachment_action_dispatch.py (an interactive_message payload with the legacy callback id reaches the listener through Bolt dispatch); tests/unit/features/incident/core/test_incident_core_new_incident_system_resolve.py (set + configured; unset + one; unset + several fails; named unconfigured fails; none fails; the error names the setting); tests/unit/server/plugins/test_server_plugins_hook_runner.py (a SettingError names its setting in plugin_boot_failed); tests/integration/server/test_lifespan_plugin_boot_failure.py or a new test (startup_warmup receives the configured systems); tests/unit/features/incident/response/test_incident_response_plugin_requirements.py (handbook requirement declared; warmup with unresolvable policy raises SettingError; production.toml and local.toml resolve to google: tests/integration/server/test_server_plugins_configuration_requirements.py also builds the [incident_response] slice and resolves the policy for each environment).
AC traceability: #1 (steps 1-3), #2 (steps 5, 5a, 5b, 6), #3 (steps 6-7), #4 (steps 4, 7), #6 (steps 5a, 5b, 7).
Assumptions: Bolt routes interactive_message to attachment_action(callback_id) (slack_bolt 1.30.0 has it; test proves it); production's INCIDENT_RESPONSE__HANDBOOK_ID SSM value is non-empty (confirmed by the human 2026-11-10).
Blast radius: boot of the whole app (the response plugin is enabled in production): a wrong policy or empty handbook id fails boot; the ECS circuit breaker (TASK-111.16) keeps the previous revision. The hookspec argument is additive. Revert restores. No deploy-checks script required (no terraform, IAM, SSM or env-name change); post-deploy: one boot with no plugin_boot_failed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: human confirmed the production SSM value of INCIDENT_RESPONSE__HANDBOOK_ID is set and non-empty (the plan's merge assumption holds). TASK-176 asked at task start: no deletes done yet (#1 SSM blobs, #4 TASK-54 open; #2 waits on TASK-182). Branch: task-145.7.2-host-prerequisites from main 8b8d1aeb.

2026-11-10: plan corrected while grounding tests: local.toml also sets new_incident_system = "google" (local supplies the Google tenant through Codespaces secrets and enables incident.response; the approved amendment wrongly said local configures Slack only).

2026-11-10 implementation (ready, uncommitted on task-145.7.2-host-prerequisites):
- Slack: register_attachment_action and legacy_action_ids / legacy_callback_ids on the registrar Protocol, PluginSlackRegistrar (prefix on the primary id only; legacy ids non-blank and unique; slack_legacy_id_registered logged at DEBUG, because observability.md allows one INFO event per boot phase) and SlackPlatformProvider (block and attachment actions share one namespace and a refused registration stores none of its ids; views keep their own; legacy_ids() lists alias -> new id for TASK-145.13; app.attachment_action attached per key). A real Bolt dispatch proves an interactive_message legacy callback id and a block_actions legacy action id reach the new listener.
- Boot: SettingError(setting, message) in contracts/configuration.py; _setting_at_fault names it. startup_warmup(logger, systems): the host reads configured systems once in lifespan and passes the same object to requirement resolution and register_feature_integrations(systems=...). Existing warmups unchanged.
- Incident: core/api.py resolve_new_incident_system (exported; build_incident_store still policy-free); incident.response startup_warmup resolves it; Requirement("incident_response.handbook_id"). production.toml and local.toml set [incident_core] new_incident_system = "google"; base.toml comment updated.
- ADRs: plugins.md (warmup systems, SettingError, presence-only requirements; Backstage and pydantic-settings sources), incident-management.md (hook named, production/local set the policy), transport-slack.md (aliases, attachment actions); dated Changes lines.
- Tests updated for intended changes: hookspec inventory signature; incident_core environment-file test now allows only new_incident_system; response requirements tuple; config check builds [incident_response] and resolves the policy for production and local; register_feature_integrations callers pass systems.
Gates (app/): ruff check . -> All checks passed!; lint-imports -> 13 kept, 0 broken; make check-package-shape -> no net-new (3 baselined); make check-test-seams -> no net-new (47 / 12 baselined); make check-settings-key-ownership -> OK; mypy -> Found 41 errors in 14 files (pre-existing, modules/ legacy; none in touched files); pytest tests --ignore=tests/smoke -> first run 4 failed (the three pinned tests above), fixed, rerun 6815 passed.
Size: ~230 production LOC, 13 code/config files + 3 ADRs (approved exception).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T18:13:00Z

---

2026-11-10 program-scope assessment (boot-policy hook), approved by the human.
Gap: the plan's "startup hookimpl" had no access to the configured systems (startup_warmup received only logger), and plugin_boot_failed named a setting only for pydantic ValidationError (boot.py _setting_at_fault).
ADRs: incident-management.md:83 decides the rule and that the declare path resolves it at startup; no ADR names the hook or how a non-pydantic error names its setting (plugins.md:109 requires the field). TASK-175's "no new hookspec argument" is scoped to register_requirements (plugins.md:111 does not restrict other hooks).
Prior tasks: TASK-172 Q3 put the policy in its own plugin, not the host; TASK-145.5.5 keeps build_incident_store policy-free. Upcoming: no second policy-among-systems setting in doc-11 or doc-15 (on-call selects by reference, oncall.md:18), so no generic host requirement kind.
Practice: Backstage plugin init receives resolved deps and throws on bad config (backstage.io/docs/backend-system/architecture/plugins); Spring @ConditionalOnSingleCandidate is the same implicit-only-when-one rule; ASP.NET IValidateOptions + ValidateOnStart; pluggy opt-in arguments make an added hookspec argument backward compatible (pluggy.readthedocs.io); pydantic-settings ignores validation context (checked locally), so a settings-model validator cannot do it.
Ruling: option A, extended in place with a size exception: startup_warmup(logger, systems), SettingError(setting) in contracts/configuration.py read by _setting_at_fault, the response plugin's startup_warmup resolves the policy. Rejected: a host-resolved requirement kind (reopens TASK-172 Q3, needs a value channel), resolving in register_background_jobs (wrong phase). Clarified: "duplicate across kinds" means block vs attachment actions; local.toml unchanged.

---
<!-- COMMENTS:END -->
