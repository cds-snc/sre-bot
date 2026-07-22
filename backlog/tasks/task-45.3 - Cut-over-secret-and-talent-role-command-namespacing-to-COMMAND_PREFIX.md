---
id: TASK-45.3
title: Cut over /secret and /talent-role command namespacing to COMMAND_PREFIX
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
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out). Swap the command-namespace source in app/modules/secret/secret.py and app/modules/role/role.py from AppSettings.PREFIX to COMMAND_PREFIX; keep existing registration and all other behavior identical. Delete the secret and role entries from app/bin/baselines/prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/secret/secret.py and app/modules/role/role.py build their slash-command name from COMMAND_PREFIX, not AppSettings.PREFIX; no other behavior changes
- [ ] #2 Pre/post command-name regression tests assert /secret and /talent-role register with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [ ] #3 secret and role baseline entries are removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
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
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX for /secret + /talent-role. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
