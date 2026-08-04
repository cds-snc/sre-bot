---
id: TASK-41
title: 'Strangler completion: delete modules/, the legacy list, and python-i18n'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-35
  - TASK-40
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1295'
priority: medium
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The "Done means" checklist of decisions/migration.md, executed once every module has migrated.

Steps:
1. Delete _register_legacy_handlers() from app/server/lifespan.py.
2. Remove "modules" from the plugin discovery paths in app/infrastructure/plugins/manager.py (walk covers packages/ only; update decisions/plugins.md check accordingly).
3. Delete app/modules/ and the legacy app/locales/*.yml catalogues.
4. Remove python-i18n from dependencies and uv.lock.
5. Empty and then delete the deprecated-client baseline + guardrail scripts (their retirement condition, per task-19).
6. Flip decisions/migration.md applies field and close its Checks; cascade rule: grep decisions/ for references.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/ does not exist; discovery paths contain only packages
- [ ] #2 grep: no _register_legacy_handlers, no python-i18n import, no import i18n outside nothing (dependency removed from lockfile)
- [ ] #3 Full smoke suite green; Slack command surface unchanged for other teams
- [ ] #4 Guardrail scripts retired; import-linter remains as the standing enforcement
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 decisions/migration.md updated per the cascade rule
- [ ] #2 Announcement note to dependent teams recorded in the PR
<!-- DOD:END -->
