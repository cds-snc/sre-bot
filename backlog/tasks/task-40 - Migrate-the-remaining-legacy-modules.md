---
id: TASK-40
title: >-
  Rebuild the remaining legacy surfaces (ops, permissions, slack, dev, sre) by
  surface into features and capabilities
status: To Do
assignee: []
created_date: 2026-07-07 19:56
updated_date: '2026-10-23T17:10:00Z'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-37
  - TASK-145
  - TASK-39
  - TASK-35
  - TASK-26.1
  - TASK-114
  - TASK-118
references:
  - decisions/migration.md
  - https://github.com/cds-snc/sre-bot/issues/1294
  - decisions/plugin-architecture.md
priority: medium
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md and migration.md: rebuild by surface, not by module. modules/sre and modules/dev are grab-bags of unrelated commands, so each surface goes to the feature, capability or host home that owns what it does, as assigned in the TASK-36 inventory (app/tests/integration/legacy_surface/INVENTORY.md), never to a module-shaped package.

Scope: every surface still under app/modules/ after TASK-37 (webhooks, including the webhook CRUD and admin views in modules/slack/ and modules/sre/webhook_helper.py), TASK-145 (incident, including /sre incident) and TASK-39 (role, secret, atip), except aws and provisioning, which TASK-88 owns (TASK-88 also deletes modules/permissions with its only callers, modules/aws/users.py and groups.py, per decisions/authorization.md). Expected remainder:
- modules/ops: log_ops_message, called by models/utils.py, utils/models.py and the legacy webhook handlers;
- modules/sre: the /sre root and /sre version (target app/server/, system info like GET /version);
- modules/dev: the /sre dev commands, dev-environment only, recorded as dropped in the inventory;
- modules/reports holds only __pycache__; delete the directory here.

Steps:
1. Order the remainder by risk x value with the maintainer; append the chosen order to this task before starting.
2. One surface or small surface group per PR series: pin first, rebuild in the standard shape (generator TASK-114, Slack handler contract TASK-26.1, translator contract TASK-118, settings slice with values in the configuration files per decisions/configuration.md, including the sre_ops values from infrastructure/configuration/features/sre_ops.py), cut over, delete.
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
