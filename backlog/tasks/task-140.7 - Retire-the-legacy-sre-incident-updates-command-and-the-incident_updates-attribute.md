---
id: TASK-140.7
title: >-
  Retire the legacy /sre incident updates command and the incident_updates
  attribute
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-08 15:01'
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
- [ ] #1 /sre incident updates answers with a pointer to /sre incident status-update, pinned in legacy_surface before and after
- [ ] #2 No code reads or writes incident_updates; INVENTORY.md rows updated
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
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
