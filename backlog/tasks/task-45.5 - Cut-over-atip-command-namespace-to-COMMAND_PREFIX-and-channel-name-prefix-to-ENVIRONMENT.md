---
id: TASK-45.5
title: >-
  Cut over atip: command namespace to COMMAND_PREFIX and channel-name prefix to
  ENVIRONMENT
status: To Do
assignee: []
created_date: '2026-07-21 19:13'
updated_date: '2026-07-22 14:58'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-45.1
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/migration.md
parent_task_id: TASK-45
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out) — atip has TWO PREFIX uses that split to different homes. (1) Command namespace at app/modules/atip/atip.py:37 (bot.command(f'/{prefix}atip'), f'/{prefix}aiprp')) -> read COMMAND_PREFIX. (2) SECOND use at atip.py:428 prefixes created CHANNEL names (dev-tmp-atip-...) -> this is NOT a command-namespace concern and must NOT read COMMAND_PREFIX; derive it from ENVIRONMENT (dev/local/ci get the 'dev-' style prefix, prod none) or an atip feature setting, per decisions/configuration.md (environment identity is orthogonal to platform-presentation config). Keep both resulting strings identical to today. Delete the atip baseline entry from prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 atip slash commands (/atip, /aiprp) build from COMMAND_PREFIX, not AppSettings.PREFIX
- [ ] #2 atip channel-name prefixing (atip.py:428) derives from ENVIRONMENT or an atip feature setting, not AppSettings.PREFIX; a test proves the created channel name is unchanged for dev vs prod
- [ ] #3 Pre/post command-name regression tests assert /atip and /aiprp register with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [ ] #4 atip baseline entry is removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/transport-slack.md and decisions/configuration.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): command-namespace read moves to infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home); atip's SECOND PREFIX use (channel-name prefixing) moves to ENVIRONMENT/atip feature setting, NOT COMMAND_PREFIX. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
