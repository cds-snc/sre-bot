---
id: TASK-145.7.2
title: >-
  Host registrar legacy aliases and attachment actions; new-incident policy
  resolver and handbook requirement
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-09T19:06:00Z'
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
- [ ] #1 register_attachment_action and legacy aliases on block and attachment actions exist in contracts/slack/registrar.py, server/plugins/slack_registrar.py and integrations/slack/provider.py; a duplicate id across kinds aborts boot; an interactive_message payload with a legacy callback id reaches its listener through Bolt dispatch (tested)
- [ ] #2 resolve_new_incident_system covers set+configured, unset+one, unset+several (fails), named-but-unconfigured (fails) and none (fails), and boot logs one CRITICAL plugin_boot_failed naming incident_core.new_incident_system (tested)
- [ ] #3 incident.response requires incident_response.handbook_id at registration; production.toml sets new_incident_system = "google" and a configuration test loads it
- [ ] #4 decisions/transport-slack.md (aliases) and decisions/incident-management.md (System selection: production sets the policy) amended with dated Changes lines; checks parent ACs #9, #10 and the alias part of #11
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human) with the Stack L program (TASK-145.7 plan). L1 in full: host prerequisites (side PR from main, any review window)
Branch task-145.7-l1-host-prerequisites from main. ~280 production LOC, 9 files, two subsystems (host Slack transport; incident response boot). Gate passes (two subsystems allowed; no mechanical move).
1. app/contracts/slack/registrar.py: register_attachment_action(callback_id, listener, *, legacy_callback_ids: Sequence[str] = ()) and a legacy_action_ids keyword on register_block_action (same semantics); docstrings name decisions/transport-slack.md:39.
2. app/server/plugins/slack_registrar.py: the plugin-prefix check (81-83) applies to the primary id only; legacy ids are exempt, must be non-blank and unique, and are logged once at registration (event slack_legacy_id_registered, fields plugin, legacy_id, id).
3. app/integrations/slack/provider.py: _attachment_actions store beside _block_actions (223); register_attachment_action; aliases stored as extra keys of the same listener; duplicate id (alias or primary, across both kinds) aborts boot as _register_listener (636) does; _attach_interaction_listeners (653) attaches app.attachment_action(id) per key; a read-only legacy_ids() listing for TASK-145.13.
4. decisions/transport-slack.md: the alias mechanism (block and attachment actions), legacy ids exempt from the prefix, listed for the contract task; Changes line.
5. app/features/incident/core/api.py (or core/systems.py if api.py nears its size): resolve_new_incident_system(policy: WorkplaceSystem | None, configured: ConfiguredSystems) -> WorkplaceSystem, pure, raising a typed error naming incident_core.new_incident_system.
6. app/features/incident/response/plugin.py: the declare-path requirement: a register_requirements entry Requirement("incident_response.handbook_id") (TASK-184) and the policy resolved in the plugin's startup hookimpl from the configured-systems read (145.5.9), so boot logs one CRITICAL plugin_boot_failed naming the key (plugins.md, TASK-172).
7. app/config/production.toml: [incident_core] new_incident_system = "google" (the only system that creates a report and video call); local.toml the same if it configures both; ci.toml keeps the plugin off (TASK-175). decisions/incident-management.md System selection: unset resolves to the only configured system, and production sets the policy explicitly; Changes line.
Tests (strict zone): tests/unit/server/plugins/test_server_slack_registrar_legacy_ids.py (alias registered and listed, prefix refused on primary only, duplicate across kinds aborts boot, blank alias refused); tests/unit/integrations/slack/test_slack_provider_attachment_action_dispatch.py (an interactive_message payload with the legacy callback id reaches the listener through Bolt dispatch); tests/unit/features/incident/core/test_incident_core_new_incident_system_resolve.py (set + configured; unset + one; unset + several fails; named unconfigured fails; none fails); tests/unit/features/incident/response/test_incident_response_plugin_requirements.py (empty handbook id fails boot naming incident_response.handbook_id; production.toml resolves to google: a configuration test loading production.toml).
AC traceability: #9 (steps 5-7), #10 (step 6), #11 aliases (steps 1-4).
Assumptions: Bolt routes interactive_message to attachment_action(callback_id) (slack_bolt installed has it; test proves it); production's INCIDENT_RESPONSE__HANDBOOK_ID SSM value is non-empty (doc-14 lists it; the legacy modal reads the same slice at incident.py:231) - human confirms before merge.
Blast radius: boot of the whole app (the response plugin is enabled in production): a wrong policy or empty handbook id fails boot; the ECS circuit breaker (TASK-111.16) keeps the previous revision. Revert restores. No deploy-checks script required (no terraform, IAM, SSM or env-name change); post-deploy: one boot with no plugin_boot_failed.
<!-- SECTION:PLAN:END -->
