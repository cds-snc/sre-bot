---
id: TASK-145.8.9
title: Shared-channel notices of status, roles and close in English and French
status: To Do
assignee: []
created_date: '2026-11-17T20:55:00Z'
updated_date: '2026-11-17T20:57:00Z'
labels:
  - incident
  - i18n
  - slack
dependencies:
  - TASK-145.8.3
references:
  - decisions/i18n.md
parent_task_id: TASK-145.8
priority: low
ordinal: 528000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
i18n.md 2026-11-17 (TASK-145.8.3 OQ3, human): a message posted to a shared conversation is in English and French, each line from its own catalogue; private replies follow the actor's locale. The update modal's field notice (TASK-145.8.3, N14) is the first consumer. This task aligns the existing single-locale channel notices of the rebuilt response surfaces: change_status's notice (TASK-145.8.4, approved AC #6 used the invoker's locale), the roles announcement (TASK-145.8.5.1) and /sre incident close's archived notice (TASK-145.8.5.3; the archive button is already bilingual). Each is a named change of kind (b) (migration.md step 4) with its pin assertion edited citing i18n.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 change_status's channel notice, the roles announcement and /sre incident close's archived notice are posted in English and French from their catalogues (one line per language, no second copy of a string)
- [ ] #2 Private replies of the same surfaces stay in the actor's locale
- [ ] #3 Each changed pin assertion cites i18n.md 2026-11-17 as a named change of kind (b), listed in the PR body
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-17T20:57:00Z

---

2026-11-17: created from TASK-145.8.3 OQ3 (human: shared-conversation posts bilingual). Plan in full at pickup; doc-11 row 18.L6c.

---
<!-- COMMENTS:END -->
