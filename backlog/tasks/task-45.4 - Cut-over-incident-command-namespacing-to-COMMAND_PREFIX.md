---
id: TASK-45.4
title: Cut over /incident command namespacing to COMMAND_PREFIX
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
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out) — largest user surface, isolated in its own PR. Swap the module-level PREFIX in app/modules/incident/incident.py (PREFIX = app_settings.PREFIX at line 25, used at line 39 for bot.command(f'/{PREFIX}incident')) to read COMMAND_PREFIX; keep registration and all other incident behavior identical. Verify no OTHER incident file derives a command name from AppSettings.PREFIX. Delete the incident baseline entry from app/bin/baselines/prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/incident/incident.py builds /incident from COMMAND_PREFIX, not AppSettings.PREFIX; no other incident behavior changes
- [ ] #2 Pre/post command-name regression tests assert /incident registers with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [ ] #3 incident baseline entry is removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
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
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX for /incident. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
