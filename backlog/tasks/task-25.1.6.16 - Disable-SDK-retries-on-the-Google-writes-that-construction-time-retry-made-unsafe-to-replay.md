---
id: TASK-25.1.6.16
title: >-
  Disable SDK retries on the Google writes that construction-time retry made
  unsafe to replay
status: To Do
assignee: []
created_date: '2026-09-11 13:59'
updated_date: '2026-09-11 14:15'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1.6
priority: high
type: bug
ordinal: 188000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-25.1.6.13 gave every Google service a construction-time retry default (GOOGLE_API_NUM_RETRIES=3), and TASK-25.1.6.14 lowered the per-attempt timeout from 60 s to 10 s. The writes below had no retries before TASK-25.1.6.13. google-api-python-client 2.198.0 retries any HTTP method on 5xx, 429, rate-limit 403 and socket errors, including timeouts, without checking idempotency. A write that landed on Google's side but timed out on ours is now sent again. Both tasks are Done, so this regression is live.

FIX: restore the pre-TASK-25.1.6.13 behavior for those writes only, by passing num_retries=0 to execute() at each call site. _DefaultingRetryHttpRequest.execute (app/integrations/google_workspace/client.py:49-51) keeps an explicit 0 and applies the default only when num_retries is None, so client.py doesn't change. The lasting fix (vendor idempotency mechanisms and a retries-disabled handle configured at construction) is TASK-87.

CALL SITES (verified 2026-09-11; re-verify when planning):
- app/packages/incident/scheduling/adapters/google_calendar.py:102 events.insert(sendUpdates="all", conferenceDataVersion=1): a replay creates a second retro event and re-sends invitations to every attendee.
- app/packages/incident/meet/adapters/google_meet.py:24 spaces.create: orphaned Meet spaces.
- app/packages/incident_draft/adapters/google_docs.py:324 files.copy: duplicate draft documents.
- app/packages/incident_draft/adapters/google_docs.py:259 documents.batchUpdate: an identical replay re-applies index-based inserts and deletes and corrupts the draft.
- app/packages/incident/documents/adapters/google_docs.py:78 apply_document_edits documents.batchUpdate: generic passthrough whose only caller sends insertText and updateParagraphStyle.
- app/infrastructure/spreadsheets/google.py:129 values.append: duplicate rows in the incident list (consumer: modules/incident/incident_folder.py:283).

NOT IN SCOPE: Drive create/copy and Directory members.insert/delete (they already retried 3 times per call before TASK-25; TASK-87); naturally idempotent writes (incident documents replace_placeholders, spreadsheets values.batchUpdate, incident drive files.update of appProperties); reads; a retries-disabled factory variant; vendor idempotency mechanisms; TASK-86's requestId fix.

SIZE NOTE: 5 production files across packages/incident, packages/incident_draft and infrastructure/spreadsheets, one identical argument per site, plus tests and one decision-record edit. This crosses the two-subsystem line, but the change is uniform and small. The planner should confirm it stays one PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each listed write call site passes num_retries=0 to execute(), and no other Google call site changes
- [ ] #2 Unit tests at each changed call site's SDK seam prove the write is issued with retries disabled
- [ ] #3 Reads and naturally idempotent writes keep the construction-time retry default; app/integrations/google_workspace/client.py is unchanged
- [ ] #4 decisions/outbound-clients.md's Migration section lists the per-call num_retries=0 override as a tolerated divergence owned by TASK-87, and its non-idempotent Google writes bullet points to TASK-87 instead of TASK-25.1.6.15 and names Drive create/copy and Directory members.insert
- [ ] #5 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-09-11 against current main)
_DefaultingRetryHttpRequest.execute (app/integrations/google_workspace/client.py:42-51) resolves `resolved_num_retries = self._default_num_retries if num_retries is None else num_retries` -- an explicit `num_retries=0` passed by a caller is honored unchanged (0 is not None). client.py needs no change; only call sites change.

Verified exact call sites (line numbers match the task description, re-confirmed by reading each file):
1. app/packages/incident/scheduling/adapters/google_calendar.py:100-110 -- `service.events().insert(calendarId=calendar_id, body=..., supportsAttachments=True, sendUpdates="all", conferenceDataVersion=1).execute()` inside `insert_event`.
2. app/packages/incident/meet/adapters/google_meet.py:24 -- `service.spaces().create(body=body).execute()` inside `create_space`.
3. app/packages/incident_draft/adapters/google_docs.py:324 -- `service.files().copy(fileId=..., body=..., supportsAllDrives=True, fields="id").execute()` inside `_copy_source_document`.
4. app/packages/incident_draft/adapters/google_docs.py:259 -- `service.documents().batchUpdate(documentId=document_id, body=body).execute()` inside `write_draft_document`.
5. app/packages/incident/documents/adapters/google_docs.py:78 -- `service.documents().batchUpdate(documentId=document_id, body=body).execute()` inside `apply_document_edits`.
6. app/infrastructure/spreadsheets/google.py:129 -- `.spreadsheets().values().append(spreadsheetId=..., range=..., body=..., valueInputOption=..., insertDataOption=...).execute()` inside `GoogleSpreadsheetProvider.append_values`.

Confirmed NOT touched (must keep plain `.execute()`, construction-time default applies):
- app/packages/incident/documents/adapters/google_docs.py:37 `replace_placeholders` (`replaceAllText`, naturally idempotent).
- app/infrastructure/spreadsheets/google.py `update_values`/`batchUpdate` (:104-118) and `read_values`/`read_cells` (reads).
- google_calendar.py `get_freebusy` (read), google_docs.py `read_sections`/`documents().get()` (reads), incident_draft `_source_name_and_folder`/`files().get()` (read).
- Repo-wide grep `rg -n "num_retries" app/packages app/infrastructure app/integrations` (run during implementation) must show only the six new sites plus the untouched `_DefaultingRetryHttpRequest`/settings/tests -- no other Google call site passes `num_retries` today, confirmed by `rg -n "\.execute\(" app/packages app/infrastructure/spreadsheets app/infrastructure/drive app/infrastructure/directory app/packages/incident_draft` showing all other calls with empty parens.

STEP 1 -- app/packages/incident/scheduling/adapters/google_calendar.py
Change the `.insert(...).execute()` call at line ~109 to `.execute(num_retries=0)`. No other line changes. A one-line comment directly above the call: "# Not naturally idempotent: a retry can create a duplicate event and re-send invitations, until a retries-disabled handle exists at construction." (revisit trigger, not a task id).
Coordinate with TASK-86, which reshapes `insert_event`'s parameters in the same function: keep the `num_retries=0` argument on the call when that reshaping lands (call is already flagged in TASK-86's own coordination note).

STEP 2 -- app/packages/incident/meet/adapters/google_meet.py
Change `.create(body=body).execute()` at line 24 to `.execute(num_retries=0)`. Same revisit-trigger comment style ("no documented idempotency key for Meet space creation").

STEP 3 -- app/packages/incident_draft/adapters/google_docs.py
- Line 324 (`_copy_source_document`): `.execute()` -> `.execute(num_retries=0)`. Comment: pre-generated ids aren't supported for Workspace file copies.
- Line 259 (`write_draft_document`'s batchUpdate): `.execute()` -> `.execute(num_retries=0)`. Comment: index-based requests corrupt the document on replay.
Leave `documents().get()` (read, line ~236) and `files().get()` in `_source_name_and_folder` untouched.

STEP 4 -- app/packages/incident/documents/adapters/google_docs.py
Line 78 (`apply_document_edits`): `.execute()` -> `.execute(num_retries=0)`. Comment: generic batchUpdate passthrough, replay may re-apply index-based edits.
Leave `replace_placeholders` (line 37, replaceAllText) and `fetch_document_content` (line 56, read) untouched -- these are the in-file negative controls.

STEP 5 -- app/infrastructure/spreadsheets/google.py
Line 129 (`append_values`'s `.execute()`): -> `.execute(num_retries=0)`. Comment: no Sheets idempotency key, replay duplicates rows.
Leave `update_values` (batchUpdate, overwrites a fixed range) and `read_values`/`read_cells` untouched -- in-file negative controls.

STEP 6 -- tests (extend existing files; no new test files)
a) app/tests/unit/packages/incident/scheduling/test_incident_scheduling_calendar_adapter.py
   - Extend `test_insert_event_builds_event_and_returns_link`: after the existing `insert.assert_called_once_with(...)`, add `insert.return_value.execute.assert_called_once_with(num_retries=0)`.
   - Add `test_get_freebusy_calls_calendar_resource_with_required_body`'s existing `query.return_value.execute.assert_called_once_with()` stays unchanged (already the negative control for the read path; do not touch).
b) app/tests/unit/packages/incident/meet/adapters/test_incident_meet_adapter.py
   - `test_create_space_returns_api_response_and_sends_expected_body`: change `create.return_value.execute.assert_called_once_with()` to `create.return_value.execute.assert_called_once_with(num_retries=0)` (this assertion currently pins zero-arg execute and will fail once the call site changes -- updating it is this task's own regression fix, not incidental scope creep).
c) app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py
   - Add `test_copy_source_document_disables_retries` near `test_copies_the_source_report_rather_than_building_a_blank_doc` (~line 272): reuse the `drive_service`/`docs_service` fixtures and `_write` helper; after a successful `_write`, assert `drive_service.files.return_value.copy.return_value.execute.assert_called_once_with(num_retries=0)`.
   - Add `test_populate_batch_update_disables_retries`: after `_write`, assert `docs_service.documents.return_value.batchUpdate.return_value.execute.assert_called_once_with(num_retries=0)`.
   - Add a negative control in the same class: assert `docs_service.documents.return_value.get.return_value.execute.assert_called_with()` (the template/draft read stays plain).
d) app/tests/unit/packages/incident/documents/test_incident_documents_adapter.py
   - Extend `test_apply_document_edits_success`: after the existing `mock_service.documents.return_value.batchUpdate.assert_called_once()`, add `mock_service.documents.return_value.batchUpdate.return_value.execute.assert_called_once_with(num_retries=0)`.
   - Extend `test_replace_placeholders_success` (negative control): add `mock_service.documents.return_value.batchUpdate.return_value.execute.assert_called_once_with()` (plain -- proves the naturally-idempotent placeholder replace is unaffected). This is the same underlying mock method (`batchUpdate`) used by both functions but each test builds its own `mock_service`, so no cross-test interference.
e) app/tests/unit/infrastructure/spreadsheets/test_google_spreadsheet_provider.py
   - Extend `test_append_values_preserves_hyperlink_formula_and_append_options`: after the existing `.append.assert_called_once_with(...)`, add `spreadsheet_service.spreadsheets.return_value.values.return_value.append.return_value.execute.assert_called_once_with(num_retries=0)`.
   - Extend `test_update_values_sends_expected_batch_body` (negative control): add `spreadsheet_service.spreadsheets.return_value.values.return_value.batchUpdate.return_value.execute.assert_called_once_with()` (plain -- update_values/batchUpdate is untouched).
All new/changed assertions follow the existing MagicMock-capture stub style already used in each file; no new fixtures or helpers are introduced. Docstrings on any new test function describe observable behavior and stub strategy only (testing-standards), no task id.

STEP 7 -- decisions/outbound-clients.md
In the Migration section (~line 61-64), replace the bullet
  "non-idempotent Google writes (Drive create and copy) issued on the retrying handle (TASK-25.1.6.15)."
with two bullets:
  "non-idempotent Google writes (Drive create/copy, Directory members.insert) issued on the retrying handle (TASK-87);"
  "a per-call num_retries=0 override at six Google writes (Calendar event insert, Meet space create, incident_draft Drive copy and Docs batchUpdate, incident documents apply_document_edits, Sheets values.append), a call-site exception to 'no retry decision repeated at call sites' tolerated until TASK-87's construction-time retries-disabled handle replaces it."
Add exactly one short dated sentence to the Changes list at the bottom: "- 2026-09-11: recorded the per-call num_retries=0 override at six non-idempotent Google writes as a tolerated divergence." No other edits to the record.

STEP 8 -- verification (from app/)
uv run ruff check .
uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
uv run pytest tests/unit/packages/incident/scheduling tests/unit/packages/incident/meet tests/unit/packages/incident_draft tests/unit/packages/incident/documents tests/unit/infrastructure/spreadsheets -q
uv run pytest tests --ignore=tests/smoke
uv run python bin/check_sdk_typing.py
Grep confirmation: `rg -n "num_retries=0" app/packages app/infrastructure/spreadsheets` shows exactly the six new sites; `rg -n "num_retries" app/integrations/google_workspace/client.py` shows no diff there.

AC TRACEABILITY (both directions)
AC#1 (each site passes num_retries=0, no other site changes) -> Steps 1-5; proven by the six new/updated `.execute.assert_called_once_with(num_retries=0)` assertions in Step 6, plus the repo-wide grep in Step 8.
AC#2 (unit tests at each seam prove retries disabled) -> Step 6 (a-e), one assertion per site.
AC#3 (reads and naturally idempotent writes keep the default; client.py unchanged) -> Steps 3-5's untouched lines, Step 6's negative-control assertions (freebusy read, replace_placeholders, update_values, docs get), and Step 8's client.py diff check.
AC#4 (decisions/outbound-clients.md Migration section updated, names Drive create/copy and Directory members.insert, points to TASK-87) -> Step 7.
AC#5 (full suite, ruff, mypy, check_sdk_typing.py pass) -> Step 8.

TEST MATRIX
Happy path: each of the six writes issues `.execute(num_retries=0)` and still returns the same success payload/shape as before (existing success-path assertions in each test are preserved, only the execute-args assertion is added/changed).
Negative control (same file, untouched site): calendar `get_freebusy` (read), incident_draft `documents().get()`/`files().get()` (reads), incident documents `replace_placeholders` (naturally idempotent), spreadsheets `update_values`/`read_values`/`read_cells` -- all still call plain `.execute()`.
Boundary: the meet adapter's existing `execute.assert_called_once_with()` assertion is the one pre-existing test that pins the old zero-arg call; updating it is itself evidence the call site changed (a pre-fix run of the new/updated tests fails against unmodified adapters).
Regression: full existing suites for each touched module still pass unmodified apart from the listed assertion additions/edits -- no behavior change to success/error-mapping paths.
Not covered (intentional, owned by TASK-87): a retries-disabled factory variant at construction, Drive create/copy and Directory members.insert/delete, deterministic event ids / 409-as-success handling, BatchHttpRequest retry.

ASSUMPTIONS AND DOUBTS FOR HUMAN REVIEW
(a) TASK-86 also touches google_calendar.py's insert_event body/signature. This task lands first or second independently; whichever lands second rebases the other's `.execute(num_retries=0)` onto its own diff (already flagged in TASK-86's own coordination note). No action needed here beyond keeping the call-site line easy to find (it is not renamed or moved by this task).
(b) The meet adapter test's `execute.assert_called_once_with()` is a real behavior-pinning assertion, not incidental scaffolding -- updating it is in-scope (it directly tests the changed call site), not opportunistic legacy-test rewriting.
(c) `apply_document_edits` and `replace_placeholders` both call `service.documents().batchUpdate(...)` on Mock services that are constructed fresh per test (`mock_get_docs_service` patch is per-test via `@patch`), so asserting different `.execute` arg shapes in each test's own mock does not require distinguishing the two call sites by inspection -- verified by reading test_incident_documents_adapter.py's per-test `@patch` fixture (each test gets its own `MagicMock()`).
(d) No production LOC estimate concern: each of the six site edits is a one-argument change (`execute()` -> `execute(num_retries=0)`) plus a one-line comment; total production diff is well under 30 LOC across 5 files.

BLAST RADIUS AND ROLLBACK
Modifies five production files (each a single-line call-site edit plus a one-line comment) and one decision record; extends five existing test files with new/changed assertions, no new test files. No settings, no lifespan, no provider wiring, no cross-package signature change (only TASK-86 touches `insert_event`'s signature, independently). A single `git revert` fully restores prior behavior (construction-time retry re-applies to these six writes). Tradeoff made explicit: after this change these six writes have zero backoff on transient 429/5xx errors until TASK-87 lands a construction-time retries-disabled handle or vendor idempotency mechanism -- a timeout or transient error on one of these calls now fails outright instead of retrying, trading replay-safety for reduced availability. This is the same tradeoff the pre-TASK-25.1.6.13 code already had for five of the six sites (Sheets append was previously unretried too, so no behavior regression versus pre-TASK-25.1.6.13 baseline for any of the six).

SIZE GATE
Production: 5 files (google_calendar.py, google_meet.py, incident_draft/google_docs.py, incident/documents/google_docs.py, infrastructure/spreadsheets/google.py) + 1 decision record, each a one-argument edit plus a one-line comment, roughly 15-20 production LOC total. Test diff: 5 existing files extended with 6 new/changed assertions and 2 new test functions, no new test files. One subsystem (Google Workspace vendor writes) touched from the call-site side only; no mechanical refactor mixed with behavior change (this is entirely a behavior change, uniformly applied). Comfortably inside the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->
