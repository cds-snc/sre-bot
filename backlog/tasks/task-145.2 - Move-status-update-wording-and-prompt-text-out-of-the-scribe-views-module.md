---
id: TASK-145.2
title: Move status-update wording and prompt text out of the scribe views module
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:23'
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
Layer A2 of TASK-145, in place in features/incident/scribe after the move. Low-risk refactor, no user-visible change.

THIS SLICE
- Delete the inline EN/FR fallback tables in entrypoints/slack_views.py (_GENERATE_NOTICES_*, _SAVE_NOTICES_*, _ORIGIN_TEMPLATES_*): every key already exists in both incident_status_update catalogues, so the views call the translator with the key only (the key is the neutral fallback). Never a second copy of a catalogue string.
- SLACK_FORMAT_INSTRUCTIONS is the summarize command's Slack-mrkdwn instruction, not status-update prompt text: it moves into scribe/service.py beside the draft prompt, the summarize service applies it itself, and handle_summarize_command stops passing it.
- build_profile_labels and build_no_new_information_wording translate catalogue keys into values the service consumes; translation stays at the edge, so they remain in the views module and are passed into the service (TASK-145.3 keeps that direction).
- The umbrella's single infrastructure.i18n import moves to core/adapters/i18n.py and is exposed as translate in core/api.py; the scribe views import it from there, so TASK-145.4 can give comms its own views module without a second import-linter ignore entry. The existing ignore entry is renamed, not added.
- Add the i18n check to the status-update locale test: no language-keyed literal table in entrypoints/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No module under scribe/entrypoints/ holds a dict keyed by locale or language; the status-update locale test asserts it
- [ ] #2 Every status-update view renders the same text as before (existing view tests pass unchanged apart from import paths)
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #4 SLACK_FORMAT_INSTRUCTIONS lives in scribe/service.py, the summarize service applies it, and no entry-point module imports or passes it
- [ ] #5 The umbrella imports infrastructure.i18n only from core/adapters/i18n.py; views call translate from core.api; the import-linter ignore list has the same number of entries
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09); paths assume TASK-145.1 merged (features/incident/...). Low-risk refactor, no user-visible change.

## Discovered state
- scribe/entrypoints/slack_views.py holds three pairs of language-keyed tables: _GENERATE_NOTICES_EN/FR (57-88: generated_note, generate_carried_forward, generate_failed, generate_unparseable, generate_security, generate_unavailable, generate_empty_history), _SAVE_NOTICES_EN/FR (89-100: saved_note, save_failed), _ORIGIN_TEMPLATES_EN/FR (102-121, keyed by StatusUpdateOrigin value plus "unknown"). Consumers: generate_notice (737), save_notice (748), origin_line (434) pick a table by locale and pass the string as the fallback to status_t(key, locale, fallback) (321), which wraps infrastructure.i18n.t(key, locale, fallback="", **variables) (infrastructure/i18n/factory.py:94). Every key exists in both catalogues (incident_status_update.en-US.yml 56-72, fr-FR 56-72, including origin.hand … origin.unknown with {author} and {time}).
- SLACK_FORMAT_INSTRUCTIONS (125-131) is the summarize command's Slack-mrkdwn instruction, passed by handle_summarize_command (entrypoints/slack.py:353) as instructions= into the summary service; the draft path already owns its own prompt text in service.py (_DRAFT_INSTRUCTIONS, 338). It is not status-update prompt text: the description's destination is corrected here to service.py.
- build_profile_labels (395) and build_no_new_information_wording (833) translate catalogue keys into values the service consumes. They are translation, so they stay in the views module and are passed into the service (the description bullet moving them is withdrawn; TASK-145.3 keeps passing translated labels into the service).
- The umbrella's only infrastructure.i18n import is slack_views.py:18, ignore entry "...scribe.entrypoints.slack_views -> infrastructure.i18n" (pyproject 305). TASK-145.4 adds a second views module (comms) that also needs the translator, and migration.md rule 3 forbids a second ignore entry. Other packages (geolocate, access/sync) import infrastructure.i18n directly and are out of scope.
- 57 other status_t / t(...) calls in the module carry English literal fallbacks (one copy each, no language keying). Same pattern; out of scope here, listed as a follow-up candidate for TASK-118.

## Steps
1. features/incident/core/adapters/i18n.py: `translate(key, locale, fallback="", **variables)` delegating to infrastructure.i18n.t; core/api.py exports translate. slack_views.py line 18 becomes `from features.incident.core.api import translate as t`. pyproject: rename the ignore entry to "features.incident.core.adapters.i18n -> infrastructure.i18n" (same count). The slack_bolt and i18n contracts are otherwise unchanged.
2. Delete the six tables. generate_notice and save_notice call status_t(key, locale, key) (the key is the neutral fallback). origin_line resolves the origin key (origin value or "unknown") and calls status_t(f"origin.{key}", locale, key, author=..., time=...) so substitution happens in the translator. Drop MappingProxyType only if unused (build_profile_labels still uses it).
3. Move SLACK_FORMAT_INSTRUCTIONS into scribe/service.py beside _DRAFT_INSTRUCTIONS as _SUMMARY_FORMAT_INSTRUCTIONS; the summarize service function appends it to the prompt itself (its instructions parameter becomes optional extra guidance, default none); handle_summarize_command stops passing instructions=. Update the slack_views __all__/imports in entrypoints/slack.py (line 93).
4. Tests: test_incident_scribe_status_update_locales.py gains test_views_module_holds_no_language_keyed_tables (ast scan of slack_views.py: no module-level name ending in _EN or _FR, no dict literal keyed by "en-US"/"fr-FR"); test_incident_scribe_summary_service.py asserts the prompt sent to the generator carries the mrkdwn instruction; new tests/unit/features/incident/core/test_incident_core_translate.py (delegation and variable substitution with a stubbed translator). Existing view tests for origin_line, generate_notice and save_notice run unchanged (same rendered text).

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 (no language-keyed tables) | 2, 4 | test_incident_scribe_status_update_locales.py |
| 2 (summary instruction owned by the service) | 3 | test_incident_scribe_summary_service.py, test_incident_scribe_summary_slack.py (handler passes no instructions) |
| 3 (translator reached through core.api; ignore list unchanged in size) | 1 | lint-imports; test_incident_core_translate.py |
| 4 (same rendered text) | 2 | test_incident_scribe_status_update_origin_line_view.py, ..._generate_view.py, ..._save_view.py unchanged and green |
| 5 | all | gates |

## Test matrix
origin_line: each origin value and None in EN and FR renders the catalogue string with author and time substituted; generate_notice and save_notice: every key in EN and FR; a missing catalogue key renders the key (fallback) rather than raising. translate: passes key, locale, fallback and variables through. Summary: prompt contains the instruction once; an explicit extra instruction is appended after it.

## Assumptions and doubts
- infrastructure.i18n.t substitutes **variables with str.format semantics (factory.py:94 signature); verify the implementation before relying on it for origin_line, otherwise keep `.format` on the translated string.
- The summarize service function's signature (service.py) has an instructions parameter; read it before step 3 and keep the public name stable for the legacy_surface registration test (test_slack_command_registration_surface.py imports the service).
- Reviewers may prefer the key-as-fallback to be an empty string; either satisfies the AC.

## Size
About 75 production lines removed and 35 added across slack_views.py, slack.py, service.py, core/api.py, core/adapters/i18n.py and pyproject. Under the gate.

## Blast radius and rollback
A missing catalogue key now shows a key instead of English; the parity test guards both catalogues. Single `git revert`.
<!-- SECTION:PLAN:END -->
