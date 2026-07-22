---
id: TASK-45.2
title: >-
  Cut over /sre and /aws command namespacing from AppSettings.PREFIX to
  COMMAND_PREFIX
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
  - decisions/migration.md
parent_task_id: TASK-45
priority: high
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out). Swap the command-namespace source in app/modules/sre/sre.py and app/modules/aws/aws.py from get_app_settings().PREFIX to the transport COMMAND_PREFIX; keep each module's existing bot.command() registration and all other behavior identical. Delete the sre and aws entries from TASK-1.3's app/bin/baselines/prefix_readers.txt in this same PR. Single, small, reviewable PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/sre/sre.py and app/modules/aws/aws.py build their slash-command name from COMMAND_PREFIX, not AppSettings.PREFIX; no other behavior changes
- [ ] #2 Pre/post command-name regression tests (mocked Bolt app) assert /sre and /aws register with the identical command string for both COMMAND_PREFIX='' and COMMAND_PREFIX='dev-'
- [ ] #3 sre and aws baseline entries are removed from app/bin/baselines/prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/transport-slack.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX in app/modules/sre/sre.py + app/modules/aws/aws.py. Pre/post command-name smoke tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, deletion tracked by TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Do not move the transport provider here — that's TASK-26.
---
<!-- COMMENTS:END -->
