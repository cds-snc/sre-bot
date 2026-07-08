---
id: TASK-35
title: Fix the dev/sre double registration (one registration path per module)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies: []
references:
  - decisions/migration.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1289'
priority: high
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/migration.md coexistence rule 4: modules register via the legacy hard-coded list OR hookimpls, never both - and it says this is fixed FIRST (live bug risk). The hard-coded _register_legacy_handlers() at app/server/lifespan.py:88-98 lists role, atip, aws, secret, sre, webhook_helper, incident, incident_helper, while the plugin discovery walk also covers modules/ (app/infrastructure/plugins/manager.py:57, base_paths=["packages", "modules"]) - so any module exposing hookimpls AND sitting in the list (sre confirmed; audit dev and the rest) registers twice.

Steps:
1. Enumerate which modules under app/modules/ expose hookimpls (grep for hookimpl decorators) and intersect with the _register_legacy_handlers() list.
2. For each overlap (sre; dev if applicable): keep the hookimpl path (the target mechanism); remove the module from the hard-coded list.
3. Verify each affected Slack command registers exactly once (log or assert registration count at startup).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No module appears in both _register_legacy_handlers() and the hookimpl discovery (startup assertion or test proves it)
- [ ] #2 A startup assertion or test proves no handler registers twice
- [ ] #3 All dev/sre commands still respond (smoke check recorded in PR)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests green
- [ ] #2 PR references decisions/migration.md rule 4
<!-- DOD:END -->
