---
id: TASK-40
title: >-
  Rebuild the remaining legacy surfaces (ops, permissions, slack, dev, sre) by
  surface into features and capabilities
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:06'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-37
  - TASK-38
  - TASK-39
  - TASK-35
  - TASK-26.1
  - TASK-114
  - TASK-118
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1294'
  - decisions/plugin-architecture.md
priority: medium
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24 to decisions/plugin-architecture.md and migration.md: rebuild by surface, not by module. modules/sre and modules/aws are grab-bags of unrelated commands, so each surface goes to the feature or capability that owns what it does, as assigned in the TASK-36 inventory, never to a module-shaped package.

Scope: every surface still under app/modules/ after TASK-37 (webhooks), TASK-38 (incident) and TASK-39 (role, secret, atip), except aws and provisioning, which TASK-88 owns. Expected remainder (verified 2026-09-24): ops, permissions, slack and dev/sre, after TASK-35 settles their registration. modules/reports holds only __pycache__ (its code was deleted by TASK-25.1.6.10.1); delete the directory here.

Steps:
1. Order the remainder by risk x value with the maintainer; append the chosen order to this task before starting.
2. One surface or small surface group per PR series: smoke first, rebuild in the standard shape (generator TASK-114, Slack handler contract TASK-26.1, translator contract TASK-118, settings in TOML), cut over, delete.
3. The python-i18n usage in each surface migrates to the translator contract with EN and FR catalogues (parity gate applies).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every remaining surface is rebuilt in its TASK-36 target (feature or capability) or recorded as deliberately dropped; smoke is green before and after each cutover; each module directory is deleted once its last surface moves and its legacy list entry is removed
- [ ] #2 No module imports python-i18n after its migration
- [ ] #3 Baselines only shrank throughout
- [ ] #4 The empty app/modules/reports directory is deleted
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 app/modules/ contains only not-yet-migrated modules at every point (no zombie halves)
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->
