---
id: TASK-41
title: 'Strangler completion: delete modules/, the legacy list, and python-i18n'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 20:06'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-35
  - TASK-37
  - TASK-38
  - TASK-39
  - TASK-40
  - TASK-88
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1295'
  - decisions/plugin-architecture.md
priority: medium
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The "Done means" checklist of decisions/migration.md, executed once every legacy surface is rebuilt (TASK-37, TASK-38, TASK-39, TASK-40, TASK-88). Updated 2026-09-24: plugins load only from pyproject entry points (TASK-110), so there are no discovery paths to edit, and app/infrastructure/plugins/ is gone (TASK-107).

Steps:
1. Delete _register_legacy_handlers() from app/server/lifespan.py.
2. Delete app/modules/ and the legacy app/locales/*.yml catalogues.
3. Remove python-i18n from dependencies and uv.lock.
4. Remove modules from the import-linter root packages and contracts (TASK-18), and retire every freeze guard whose baseline is now empty, with its script, baseline, make target and CI step.
5. Flip decisions/migration.md applies field and close its Checks; cascade rule: grep decisions/ for references.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/ does not exist; plugins load only from pyproject entry points and _register_legacy_handlers() is gone
- [ ] #2 grep: no _register_legacy_handlers and no python-i18n import in app/; python-i18n removed from the lockfile; app/locales/ deleted
- [ ] #3 Full smoke suite green; Slack command surface unchanged for other teams
- [ ] #4 Guardrail scripts with empty baselines are retired; import-linter remains as the standing enforcement and no longer lists modules
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 decisions/migration.md updated per the cascade rule
- [ ] #2 Announcement note to dependent teams recorded in the PR
<!-- DOD:END -->
