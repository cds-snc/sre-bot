---
id: TASK-45
title: >-
  Retire AppSettings.PREFIX: introduce SLACK__COMMAND_PREFIX transport setting
  and migrate legacy command namespacing
status: Done
assignee: []
created_date: '2026-07-21 19:12'
updated_date: '2026-07-24 13:15'
labels:
  - phase-0
  - security
  - slack
milestone: m-0
dependencies:
  - TASK-1.3
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/migration.md
  - decisions/platform-transports.md
  - 'https://github.com/cds-snc/sre-bot/issues/1316'
priority: high
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational cleanup that unblocks the settings-home consolidation. AppSettings.PREFIX is overloaded — after TASK-1.2.3 it carries no environment meaning but is still the slash-command namespace read by 6 frozen modules (atip, aws, incident, role, secret, sre). This initiative introduces the transport-owned COMMAND_PREFIX (env SLACK__COMMAND_PREFIX) in the Slack transport settings home app/infrastructure/slack/settings.py (per decisions/transport-slack.md and configuration.md), migrates every legacy command-namespace read from AppSettings.PREFIX to COMMAND_PREFIX one module at a time behind pre/post command-name smoke tests (the migration.md freeze carve-out), and deletes AppSettings.PREFIX when the last module cuts over. This reverses the earlier 'PREFIX retirement out of scope / no legacy file touched' stance — the three governing decision records (migration.md, transport-slack.md, configuration.md) were amended in the same change to record the bounded freeze carve-out. Executed as many small reviewable PRs (one foundational slice, per-module cutovers, one teardown). Ratchet: TASK-1.3's app/bin/baselines/prefix_readers.txt is the retirement tracker — each cutover PR deletes its baseline entry. Scope boundary: platforms.py retirement stays with TASK-24; atip's SECOND PREFIX use (channel-name prefixing) is migrated to ENVIRONMENT/atip-setting, NOT COMMAND_PREFIX.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 COMMAND_PREFIX exists as SLACK__COMMAND_PREFIX on the Slack transport settings in app/infrastructure/slack/settings.py with a cached provider, default '' (prod), and is set in every deployment manifest (terraform/, CI, local compose/env examples) to the SAME value as PREFIX per environment during coexistence
- [x] #2 Every legacy module (atip, aws, incident, role, secret, sre) reads COMMAND_PREFIX instead of AppSettings.PREFIX for slash-command naming; each cutover shipped as its own PR with pre/post command-name smoke tests proving the resulting command string is unchanged
- [x] #3 atip's channel-name prefixing (app/modules/atip/atip.py:428) no longer reads AppSettings.PREFIX; it derives from ENVIRONMENT or an atip feature setting, with a test proving dev vs prod channel naming is unchanged
- [x] #4 AppSettings.PREFIX and its aggregator mirror (app/infrastructure/configuration/settings.py) and the lifespan diagnostic field are deleted once the last module cuts over; TASK-1.3's prefix_readers.txt baseline is empty and the guardrail still passes
- [x] #5 grep -rn 'AppSettings().PREFIX|app_settings.PREFIX|get_app_settings().PREFIX' app/ --include=*.py returns no hits after teardown
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR series references decisions/transport-slack.md and decisions/configuration.md
- [x] #2 Each per-module PR has green pre/post command-name smoke tests
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @planner
created: 2026-07-21 19:15
---
Governance: this initiative reverses the earlier 'PREFIX retirement out of scope / no legacy file touched' stance. Per governance.md cascade rule, decisions/migration.md, decisions/transport-slack.md, and decisions/configuration.md were amended in the same change to record the bounded freeze carve-out (PREFIX command-namespace retirement is permitted inside frozen modules, per-module, behind pre/post command-name smoke tests). Sequencing: TASK-45.1 (foundational, no module edits) -> TASK-45.2/.3/.4/.5 (per-module cutovers, parallelizable after .1) -> TASK-45.6 (teardown). Ratchet tracker is TASK-1.3's app/bin/baselines/prefix_readers.txt; each cutover deletes its entry. First slice (TASK-45.1) is planned in detail; per-module slices are scoped and will be planned when picked up. platforms.py deletion stays with TASK-24.
---

author: @task-planner
created: 2026-07-22 14:39
---
Architecture alignment (2026-07-22): decisions/configuration.md now explicitly states the god-settings aggregator (app/infrastructure/configuration/settings.py Settings/get_settings()/settings_map) is being removed by an open PR, not grown — no new/open task may wire a settings slice into it. Two follow-ups for this task when next reviewed: (1) AC #1's 'local compose/env examples' wording is inaccurate — there is no .env.example or compose PREFIX setting in this repo; the real local coexistence anchor is app/Makefile's dev/debug targets (PREFIX="dev-"), as corrected in TASK-45.1's plan. (2) AC #4 assumes app/infrastructure/configuration/settings.py (the aggregator mirror of PREFIX) still exists at teardown time (TASK-45.6) — since a separate PR may delete that whole file first, TASK-45.6 must verify the file's existence before editing specific lines/fields.
---

author: @copilot
created: 2026-07-22 14:58
---
Alignment guidance (2026-07-22) for all subtasks — captured here since each subtask runs in a fresh session. (1) Settings source: the slash-command prefix comes from the transport settings home infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (created in TASK-45.1), NOT AppSettings.PREFIX and NOT the provider. (2) Test hygiene: new/updated tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings — it is the dead third settings duplicate slated for deletion (TASK-24). Use integrations.slack.settings.SlackSettings (target home) or a lightweight attribute stub (SimpleNamespace / the MockSlackSettings pattern in app/tests/unit/integrations/slack/conftest.py). (3) Layer note: SlackPlatformProvider still lives in the mislocated app/integrations/slack/provider.py; the transport move to app/infrastructure/slack/ is TASK-26 — do not relocate the transport in a 45.* cutover. Verified against decisions/transport-slack.md + platform-transports.md.
---
<!-- COMMENTS:END -->
