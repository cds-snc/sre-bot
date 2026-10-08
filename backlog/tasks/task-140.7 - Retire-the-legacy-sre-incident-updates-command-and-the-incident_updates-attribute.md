---
id: TASK-140.7
title: >-
  Retire the legacy /sre incident updates command and the incident_updates
  attribute
status: In Progress
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-08 15:28'
labels:
  - incident
dependencies:
  - TASK-140.6
  - TASK-140.8.1
parent_task_id: TASK-140
priority: medium
type: chore
ordinal: 326000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/migration.md: pin the surface, cut over to /sre incident status-update, remove the legacy registration and the incident_updates read and write paths in modules/incident, and update the legacy_surface INVENTORY. Legacy /sre incident status (internal lifecycle state) stays until TASK-38.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /sre incident updates answers with a pointer to /sre incident status-update, pinned in legacy_surface before and after
- [x] #2 No code reads or writes incident_updates; INVENTORY.md rows updated
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Decisions (human, 2026-10-08)
- Stored `incident_updates` data stays in DynamoDB: no migration, no copy. Reads tolerate it. Its fate is recorded in TASK-38.5 and TASK-38.7 notes.
- `Incident` (models/incidents.py) drops the field and gains a `model_validator(mode="before")` that pops the legacy key; `extra="forbid"` stays.
- `/sre incident updates` (any action, or none) answers with one bilingual pointer. EN: "`/sre incident updates` has been retired. Use `/sre incident status-update` to draft, review and approve a public status update." FR: "`/sre incident updates` a été retirée. Utilisez `/sre incident status-update` pour rédiger, réviser et approuver une mise à jour publique."
- The deprecated `summary` and `add_summary` commands are deleted with their handlers and resource keys; they fall to "Unknown command".
- Imports at module top level only, tests included (ruff PLC0415; also grep for inline `__import__` and importlib). A circular import is a design flaw to fix, not a reason for a lazy import. New tests live in the layered tree; legacy test files are edited in place only.

## Findings
- Every incident row carries `incident_updates` (`create_incident` dumps the model, default `[]`), and `information_display.py:29` and `information_update.py:329` rebuild `Incident(**row)` with `extra="forbid"`. Deleting the field without tolerance would break the information and field-update modals for all incidents.
- Nothing else reads the attribute: no exports, documents, retros, Terraform, app/bin, locales or docs. Only `fetch_updates` and the model.
- Surface in modules/incident/incident_helper.py: help text (lines 58, 83, 106, 131), `register` line 165 (`incident_updates_view`), resource key `updates` (195), `summary`/`add_summary` keys, `handle_updates` (408), legacy handlers (449-464), dialog/submission/display code (667-740).
- modules/incident/incident_folder.py: `current_time_est`, `store_update`, `fetch_updates` (539-583); `fetch_updates` also returns None when a record has no updates (removed with it).
- modules/incident/core.py:587 next-steps line; INVENTORY.md row `incident_updates_view` (line 64) and all `incident_helper.py:NNN` line refs; decisions/incident-management.md:152 tolerated bullet.

## Steps (two commits; implementation pauses after step 1 for the human to commit)
1. Pin before (tests only, green on current code). New `app/tests/integration/legacy_surface/test_incident_updates_command_surface.py` using `build_harness`/`dispatch("sre", "incident ...")`: `updates add` opens a modal with callback_id `incident_updates_view`; `updates show` posts stored updates; bare `updates` answers help; `add_summary` and `summary` answer their deprecation notice then behave as add/show. Run the whole legacy_surface suite. STOP for the human to commit.
2. incident_helper.py: delete `open_updates_dialog`, `handle_updates_submission`, `display_current_updates`, `_store_unavailable_view`, `handle_legacy_add_summary`, `handle_legacy_summary`, the `summary`/`add_summary` keys, the `incident_updates_view` registration and the unused `json` import. Replace `handle_updates` with a small pointer handler (same signature, `respond` only, bilingual text above); keep the `updates` resource key. Drop the `updates` lines and example from EN and FR help, add `/sre incident status-update` to the examples, and drop `summary`/`add_summary` from the legacy-commands lists.
3. incident_folder.py: delete `current_time_est`, `store_update`, `fetch_updates` and whatever ruff reports as newly unused (`pytz`, `build_dynamodb_adapter`, `_failure_fields`, `_unclassified_fields`, `ClientError`).
4. models/incidents.py: remove the field; add the before-validator that drops the legacy key (named constant). core.py:587: replace the line with "• `/sre incident status-update` - Draft, review and approve a public status update".
5. INVENTORY.md: delete the `incident_updates_view` row; fix the totals (11 views, 4 events, 33 interactions); renumber every `incident_helper.py:NNN` row; add a provider-registered row for the `/sre incident updates` pointer (pinned by the new test file, `-k incident_updates`) and a row for `/sre incident status-update` (scribe hookimpl, pinned by `test_registered_command_tree_is_unchanged`). Remove the tolerated bullet at decisions/incident-management.md:152 and add a Changes entry.
6. Pin after: flip the new test file: `updates add`, `updates show`, bare `updates` answer the pointer with no modal opened and no DynamoDB call; `summary` and `add_summary` are no longer handled (Unknown command reply); `status-update` still registered.
7. Edit legacy tests in place: test_incident_helper.py (delete handle_updates, dialog, submission, display and store-unavailable tests, and the add_summary/summary tests; add pointer and unknown-command assertions), test_incident_folder.py (delete store_update/fetch_updates tests), test_incident_core.py:119 (new line), test_information_display.py (drop `incident_updates` from fixtures; add a case where a stored row still carries it and the modal opens). New unit test `tests/unit/models/test_models_incident_legacy_attribute_load.py`: legacy key loads, unknown key still raises, `model_dump()` has no `incident_updates`.
8. Gates from app/: ruff check, mypy (0 errors in touched files), lint-imports, `pytest tests --ignore=tests/smoke` (6 known TASK-90 single-process failures are not ours), legacy_surface suite before and after, greps for inline `__import__`/importlib and a final `rg incident_updates app/`.

## AC traceability
- AC1: steps 1, 2, 6 (pointer pinned before and after).
- AC2: steps 2-5, 7 and the final grep (the model validator constant is the only remaining mention).
- AC3: step 8.

## Size and blast radius
- Production: 4 files (incident_helper.py, incident_folder.py, models/incidents.py, core.py), about 150 LOC removed and 25 added; plus INVENTORY.md and the decision record. Tests: about 5 files edited, 2 new. One subsystem, net deletion, no mechanical refactor mixed in. Within the single-PR gate.
- Rollback: one `git revert` restores the command and registration; DynamoDB data is never touched. In-flight `incident_updates_view` modals get no handler after deploy (negligible). Modals opened before deploy and submitted after still load because of the validator. No Terraform or config ordering constraints.
- Users of `summary` and `add_summary` get "Unknown command" (human decision).

## Assumptions to verify
- The provider routes `/sre incident updates ...` to the legacy handler (proved by the step 1 pin).
- The pointer needs no `ack` (existing legacy handlers only `respond`).
- Which imports become unused after deletions (ruff reports).

Approved by the human on 2026-10-08.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Step 1 (pin before): app/tests/integration/legacy_surface/test_incident_updates_command_surface.py, 8 tests green on current code. The legacy /sre handler posts through modules.sre.platforms.slack.client (LegacySlackBootstrap().web), so the test fixture swaps it for the harness fake client. The SRE wrapper posts only the last respond() text to response_url, or 'Incident command executed' when the handler never calls respond. Mutation checks (modal, show, deprecation and help each no-op'd) fail exactly the tests that cover them. cd app && uv run pytest tests/integration/legacy_surface -q -> 28 passed, 4 warnings in 0.37s. ruff check: All checks passed!

Steps 2-8 done (2026-10-08). Tests flipped first (failing on old code: surface file 6, test_incident_helper 6, test_incident_core 1, test_information_display 1, new model test 3), then implementation.
Changes: incident_helper.py: UPDATES_RETIRED_POINTER constant; handle_updates answers it via respond only; dialog, submission, display, store-unavailable view, add_summary/summary handlers and keys, incident_updates_view registration and json import deleted; EN/FR help updated. incident_folder.py: current_time_est, store_update, fetch_updates, _failure_fields, _unclassified_fields and the pytz, build_dynamodb_adapter, ClientError, OperationResult imports deleted. models/incidents.py: field removed, before-validator _drop_retired_incident_updates drops _RETIRED_INCIDENT_UPDATES_KEY, extra=forbid kept. core.py next-steps line now points to /sre incident status-update. INVENTORY.md: incident_updates_view row deleted, totals 18 actions / 11 views / 4 events / 33 interactions, incident_helper.py refs renumbered 151-167, rows added for /sre incident status-update and the /sre incident updates pointer; also fixed stale scribe refs slack.py:85/104 -> 117/136. decisions/incident-management.md: tolerated bullet removed, 2026-10-08 Changes entry. TASK-38.4 description: incident_updates_view dropped from scope.
Gates (cd app):
- uv run ruff check . -> All checks passed!
- uv run ruff format --check (10 touched .py) -> 10 files already formatted
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 57 errors in 20 files (checked 384 source files). Touched files: 0 in models/incidents.py, incident_helper.py, incident_folder.py and all touched tests; 9 pre-existing in modules/incident/core.py (lines 79, 97, 103, 110, 121, 137, 165, 220, 554), all above the only edit (a string at line 587); no new errors.
- uv run pytest tests/integration/legacy_surface -q -> 26 passed, 4 warnings
- uv run pytest tests --ignore=tests/smoke -q -p no:randomly -> 4249 passed, 1898 warnings in 54.73s (no TASK-90 failures since #1560).
- rg incident_updates app/ outside tests -> only models/incidents.py (constant, validator name, docstring).
- rg '__import__|importlib' on touched files -> no matches.

Follow-up (human, 2026-10-08): fixed the 9 pre-existing mypy errors in modules/incident/core.py in this PR (still 2 files: core.py and test_incident_core.py). Annotation fixes: _get_existing_bookmarks returns dict[str, str] with a typed bookmarks list; _find_product_folder returns str | None; the bookmark helpers take dict[str, str]; _create_document_bookmark takes folder_id: str | None; meeting_uri and folder_id typed locals; document_link starts as "" (always assigned before use). Bug fix: a security incident with SLACK_SECURITY_USER_GROUP_ID unset called usergroups_users_list(usergroup=None), which raises and stops the declare partway through; it now skips the group invite and logs security_user_group_not_configured. New test test_security_incident_without_a_configured_security_group_skips_the_group_invite (failed before the fix); the two existing security-group tests now pin the group id so they don't depend on the environment.
Gates (cd app):
- uv run ruff check modules/incident/core.py -> All checks passed!
- uv run ruff format --check (core.py, test_incident_core.py) -> 2 files already formatted
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files (was 57 in 20); 0 in every touched file.
- uv run pytest tests --ignore=tests/smoke -q -p no:randomly -> 4250 passed, 1898 warnings in 49.01s
- uv run pytest tests/integration/legacy_surface -q -> 26 passed, 4 warnings
<!-- SECTION:NOTES:END -->
