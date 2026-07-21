---
id: TASK-45.1
title: >-
  Stand up app/infrastructure/slack transport settings home with COMMAND_PREFIX
  and central prefix application
status: To Do
assignee: []
created_date: '2026-07-21 19:13'
updated_date: '2026-07-21 19:14'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-1.3
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/platform-transports.md
parent_task_id: TASK-45
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational slice (no frozen-module edits yet). Create the Slack transport settings home app/infrastructure/slack/settings.py with a SlackTransportSettings BaseSettings exposing COMMAND_PREFIX: str = '' (env SLACK__COMMAND_PREFIX, nested delimiter per configuration.md) and a cached get_slack_transport_settings() provider. Wire it into the settings aggregator alongside the other slices. Apply COMMAND_PREFIX centrally for hookspec-registered commands at registration/compose time (infrastructure/plugins manager register_slack_commands path) so migrated/new commands get the prefix in one place. Set SLACK__COMMAND_PREFIX in terraform/, CI (ci_code.yml env), and local compose/.env examples to the SAME value as PREFIX per environment (dev- in dev, '' in prod) for coexistence. No app/modules/** file changes in this slice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/slack/settings.py defines SlackTransportSettings with COMMAND_PREFIX (env SLACK__COMMAND_PREFIX, default '') and a cached get_slack_transport_settings() provider; invalid config fails boot with a pydantic error
- [ ] #2 The transport applies COMMAND_PREFIX once, centrally, to hookspec-registered Slack commands at registration; a unit test asserts a base command name 'sre' registers as '<COMMAND_PREFIX>sre'
- [ ] #3 SLACK__COMMAND_PREFIX is set in terraform/ task definition, .github/workflows/ci_code.yml, and local compose/.env examples, matching PREFIX per environment
- [ ] #4 No file under app/modules/ is modified in this slice; AppSettings.PREFIX still exists and is untouched
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Verified anchors (2026-07-21): app/infrastructure/slack/ does NOT exist yet (this slice creates it as the transport settings home, first concrete piece of the eventual transport consolidation). Existing Slack credential/transport-vendor settings live in app/integrations/slack/settings.py::SlackSettings using FLAT aliases (SLACK_BOT_TOKEN etc.) — COMMAND_PREFIX is a transport-presentation concern and per decisions/configuration.md + transport-slack.md belongs in the infrastructure/slack transport home, NOT in integrations/slack. Central registration point confirmed: features register base command names through SlackPlatformProvider.register_command(command='aws', ...) at app/integrations/slack/provider.py:658, driven by the register_slack_commands hookspec fired in app/infrastructure/plugins/manager.py:89. That provider is the single place that turns a base name into a Bolt slash command — the correct, one-place home to prepend COMMAND_PREFIX.

Step 1 — Settings home (AC #1). Create app/infrastructure/slack/__init__.py and app/infrastructure/slack/settings.py with SlackTransportSettings(BaseSettings): COMMAND_PREFIX: str = '' aliased to env SLACK__COMMAND_PREFIX (use env_nested_delimiter='__' or explicit alias='SLACK__COMMAND_PREFIX'; match the nested convention configuration.md mandates), model_config extra='ignore'. Add cached get_slack_transport_settings() provider (lru_cache, singleton pattern per settings-singleton skill). Unit test: valid default '' ; SLACK__COMMAND_PREFIX='dev-' is read; provider returns a singleton.

Step 2 — Aggregator wiring. Register the new slice in app/infrastructure/configuration/settings.py's Settings.__init__ settings_map (add key 'slack_transport' -> get_slack_transport_settings) and a typed field, mirroring the existing slices. Keep it additive; do not touch the flat SlackSettings.

Step 3 — Central prefix application (AC #2). In SlackPlatformProvider.register_command (app/integrations/slack/provider.py:658), read get_slack_transport_settings().COMMAND_PREFIX once and prepend it when the base command is materialized into the Bolt slash command (the f'/{command}' construction — locate the exact bot.command wiring below line 658 and apply there so BOTH the registered Bolt command and the help/registry name stay consistent). Apply exactly once, centrally; handlers and features keep declaring base names ('sre','aws'). Guard: prefix applied only to hookspec-registered commands (legacy modules still build their own f-string until their TASK-45.x cutover — do not double-prefix). Unit test: register_command(command='sre') with COMMAND_PREFIX='dev-' registers '/dev-sre'; with '' registers '/sre'.

Step 4 — Manifests (AC #3). Set SLACK__COMMAND_PREFIX in: terraform/ ECS task definition (same place ENVIRONMENT was set by TASK-1.1), .github/workflows/ci_code.yml env block, and local compose/.env.example. Value = the SAME as PREFIX per environment (dev- in dev, '' in prod/ci) for coexistence per transport-slack.md.

Step 5 — Freeze respected (AC #4). No app/modules/** file is edited in this slice; AppSettings.PREFIX is untouched. TASK-1.3 baseline is unchanged by this slice (no reader removed yet).

Test matrix: AC#1 -> Step 1 settings unit tests (default, env override, singleton, invalid->pydantic error). AC#2 -> Step 3 central-prefix unit test (dev- and '' cases). AC#3 -> manifest grep/CI presence check. AC#4 -> guardrail (TASK-1.3) still green + grep shows no app/modules edit.

Doubts to verify in implementation: (a) exact Bolt-command construction site inside/after register_command (line 658+) — confirm whether the slash string is built there or delegated to commands.py/bootstrap.py; apply the single prefix at the true construction point. (b) Whether help/registry names must also reflect the prefix (they should, for consistency) — assert in the unit test. (c) env_nested_delimiter vs explicit alias: pick whichever keeps SlackTransportSettings independent of the flat SlackSettings aliasing; do not retrofit SlackSettings here.

Blast radius: new app/infrastructure/slack/ package (settings only), one aggregator wiring edit, one provider edit (central prefix), manifests, tests. No frozen-module edit, no PREFIX deletion. Rollback: revert PR; COMMAND_PREFIX defaults '' so behavior is identical to today until a module cuts over.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/transport-slack.md and decisions/configuration.md
<!-- DOD:END -->
