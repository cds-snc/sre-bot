---
id: TASK-145.2
title: Move status-update wording and prompt text out of the scribe views module
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.1
parent_task_id: TASK-145
priority: high
type: chore
ordinal: 352000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A2 of TASK-145, in place in features/incident/scribe after the TASK-144 stack is merged. Mechanical, no behaviour change.

THIS SLICE
- Delete the inline EN/FR fallback tables in entrypoints/slack_views.py (_GENERATE_NOTICES_*, _SAVE_NOTICES_*, _ORIGIN_TEMPLATES_*): every key already exists in both incident_status_update catalogues, so the views call the translator with the key only. One neutral fallback at most, never a second copy of a catalogue string.
- Move SLACK_FORMAT_INSTRUCTIONS (model prompt text) into status_update_prompt.py; the service passes it, the handler no longer does.
- Move build_profile_labels and build_no_new_information_wording out of the views module: labels are built in comms_profile.py from the catalogue, the no-new-information wording in status_update.py; the handlers stop assembling service inputs from view helpers.
- Add the i18n check to the status-update locale test: no language-keyed literal table in entrypoints/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No module under scribe/entrypoints/ holds a dict keyed by locale or language; the status-update locale test asserts it
- [ ] #2 SLACK_FORMAT_INSTRUCTIONS lives in status_update_prompt.py and no entry-point module imports it
- [ ] #3 build_profile_labels lives in comms_profile.py and build_no_new_information_wording in status_update.py; slack_views.py imports them, not the reverse
- [ ] #4 Every status-update view renders the same text as before (existing view tests pass unchanged apart from import paths)
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
