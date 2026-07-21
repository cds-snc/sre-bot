---
id: TASK-45
title: >-
  Retire AppSettings.PREFIX: introduce SLACK__COMMAND_PREFIX transport setting
  and migrate legacy command namespacing
status: To Do
assignee: []
created_date: '2026-07-21 19:12'
updated_date: '2026-07-21 19:15'
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
priority: high
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational cleanup that unblocks the settings-home consolidation. AppSettings.PREFIX is overloaded — after TASK-1.2.3 it carries no environment meaning but is still the slash-command namespace read by 6 frozen modules (atip, aws, incident, role, secret, sre). This initiative introduces the transport-owned COMMAND_PREFIX (env SLACK__COMMAND_PREFIX) in the Slack transport settings home app/infrastructure/slack/settings.py (per decisions/transport-slack.md and configuration.md), migrates every legacy command-namespace read from AppSettings.PREFIX to COMMAND_PREFIX one module at a time behind pre/post command-name smoke tests (the migration.md freeze carve-out), and deletes AppSettings.PREFIX when the last module cuts over. This reverses the earlier 'PREFIX retirement out of scope / no legacy file touched' stance — the three governing decision records (migration.md, transport-slack.md, configuration.md) were amended in the same change to record the bounded freeze carve-out. Executed as many small reviewable PRs (one foundational slice, per-module cutovers, one teardown). Ratchet: TASK-1.3's app/bin/baselines/prefix_readers.txt is the retirement tracker — each cutover PR deletes its baseline entry. Scope boundary: platforms.py retirement stays with TASK-24; atip's SECOND PREFIX use (channel-name prefixing) is migrated to ENVIRONMENT/atip-setting, NOT COMMAND_PREFIX.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 COMMAND_PREFIX exists as SLACK__COMMAND_PREFIX on the Slack transport settings in app/infrastructure/slack/settings.py with a cached provider, default '' (prod), and is set in every deployment manifest (terraform/, CI, local compose/env examples) to the SAME value as PREFIX per environment during coexistence
- [ ] #2 Every legacy module (atip, aws, incident, role, secret, sre) reads COMMAND_PREFIX instead of AppSettings.PREFIX for slash-command naming; each cutover shipped as its own PR with pre/post command-name smoke tests proving the resulting command string is unchanged
- [ ] #3 atip's channel-name prefixing (app/modules/atip/atip.py:428) no longer reads AppSettings.PREFIX; it derives from ENVIRONMENT or an atip feature setting, with a test proving dev vs prod channel naming is unchanged
- [ ] #4 AppSettings.PREFIX and its aggregator mirror (app/infrastructure/configuration/settings.py) and the lifespan diagnostic field are deleted once the last module cuts over; TASK-1.3's prefix_readers.txt baseline is empty and the guardrail still passes
- [ ] #5 grep -rn 'AppSettings().PREFIX|app_settings.PREFIX|get_app_settings().PREFIX' app/ --include=*.py returns no hits after teardown
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR series references decisions/transport-slack.md and decisions/configuration.md
- [ ] #2 Each per-module PR has green pre/post command-name smoke tests
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @planner
created: 2026-07-21 19:15
---
Governance: this initiative reverses the earlier 'PREFIX retirement out of scope / no legacy file touched' stance. Per governance.md cascade rule, decisions/migration.md, decisions/transport-slack.md, and decisions/configuration.md were amended in the same change to record the bounded freeze carve-out (PREFIX command-namespace retirement is permitted inside frozen modules, per-module, behind pre/post command-name smoke tests). Sequencing: TASK-45.1 (foundational, no module edits) -> TASK-45.2/.3/.4/.5 (per-module cutovers, parallelizable after .1) -> TASK-45.6 (teardown). Ratchet tracker is TASK-1.3's app/bin/baselines/prefix_readers.txt; each cutover deletes its entry. First slice (TASK-45.1) is planned in detail; per-module slices are scoped and will be planned when picked up. platforms.py deletion stays with TASK-24.
---
<!-- COMMENTS:END -->
