---
id: TASK-40
title: Migrate the remaining legacy modules
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-37
  - TASK-38
  - TASK-39
references:
  - decisions/migration.md
priority: medium
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Complete the strangler for every module still under app/modules/ after tasks 37-39. Current inventory: atip, aws, dev, incident, ops, permissions, provisioning, reports, role, secret, slack, sre, webhooks - so the expected remainder here is aws, ops, permissions, provisioning, reports, slack, plus whatever of dev/sre needs more than the task-35 cleanup. Consult the task-36 inventory for the authoritative list.

Steps:
1. Order the remainder by risk x value with the maintainer; append the chosen order to this task before starting.
2. One module per PR series, per-module recipe (smoke first, package, cutover, delete).
3. python-i18n usage inside each module migrates to the infrastructure/i18n stack with EN/FR catalogues (parity gate applies).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every migrated module: smoke green pre/post, directory deleted, legacy list entry removed
- [ ] #2 No module imports python-i18n after its migration
- [ ] #3 Baselines only shrank throughout
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 app/modules/ contains only not-yet-migrated modules at every point (no zombie halves)
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->
