---
id: TASK-25.1.5.1
title: >-
  Repoint incident_draft's Drive calls onto get_drive_service with an inline
  adapter boundary
status: To Do
assignee: []
created_date: '2026-09-02 13:26'
updated_date: '2026-09-02 16:05'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.5
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.5
priority: high
ordinal: 131000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-25.1.5 on 2026-09-02 because bundling it tripped the single-PR size gate. TASK-25.1.5 migrates the google_drive.py vendor module onto the stub-typed DriveResource; this slice moves the ONE real adapter among Drive's nine production consumers onto the vendor package's factory + its own inline try/except, per decisions/outbound-clients.md ("the adapter is the boundary", one adaptation tier).

app/packages/incident_draft/adapters/google_docs.py is the only app/packages/<feature>/adapters/ file that calls Drive (grep-confirmed 2026-09-02). It has two Drive call sites, both against functions that are pure SDK mirrors adding no domain value:
- :272 _copy_source_document -> google_drive.create_file_from_template(draft_title, folder, source_document_id, fields="id")
- :1245 -> google_drive.get_file_by_id(document_id, fields="id, name, parents")
It also calls google_drive.find_files_by_name, which builds a Drive q-DSL query and is genuine domain logic - that call stays on the vendor module.

Scope:
1. Repoint the two call sites onto integrations.google_workspace.client.get_drive_service(scopes=..., delegated_user_email=...) with the adapter's own try/except + classify_google_error, dropping their dependency on execute_google_api_request. This is the first Google call site in the repo to satisfy decisions/outbound-clients.md's adapter contract properly, and directly discharges part of TASK-25.1.6's AC#2.
2. Delete integrations/google_workspace/google_drive.py::get_file_by_id, which has zero remaining callers once step 1 lands (grep-confirmed: the adapter is its only consumer).
3. Leave create_file_from_template in place: modules/incident/incident_document.py:29 still calls it and is legacy app/modules/* with no adapter tier. Its retirement belongs to TASK-25.1.6's adapter work, not here.

SIZE WARNING for whoever plans this: app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py is 1704 lines with 135 mock_drive references, all patching packages.incident_draft.adapters.google_docs.google_drive as one module-level mock. Step 1 splits that boundary in two (a mocked DriveResource chain for the two repointed calls, the existing module mock for find_files_by_name) and invalidates shape assertions such as mock_drive.create_file.assert_not_called(). Expect the test rework, not the production change, to dominate this PR - plan a single shared DriveResource fake helper rather than reinventing the chain per test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident_draft/adapters/google_docs.py builds its Drive calls from integrations.google_workspace.client.get_drive_service and wraps them in its own try/except + classify_google_error; neither Drive call site depends on execute_google_api_request or on a google_drive passthrough
- [ ] #2 integrations/google_workspace/google_drive.py::get_file_by_id is deleted, grep-verified zero callers repo-wide
- [ ] #3 create_file_from_template is left in place in google_drive.py for its remaining legacy modules/incident/incident_document.py caller; the adapter does not call google_drive.find_files_by_name today (repo-wide grep confirms zero calls under app/packages/incident_draft -- the task description's premise was incorrect) and this slice does not add one
- [ ] #4 tests/unit/packages/incident_draft/test_incident_draft_adapter.py is reworked onto the split mock boundary with a single shared DriveResource fake helper; every existing behavioral assertion is preserved or has a documented equivalent, and error-classification coverage is added for the two repointed call sites
- [ ] #5 TASK-25.1.6's call-site inventory is updated to record that these two sites are discharged (AC#2 bucket) and to remove them from its outstanding scope
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-02, re-verified against current code, not the task's prose alone):

- TASK-25.1.5 (parent, Drive vendor-module migration) is Done -- google_drive.py already calls
  integrations.google_workspace.client.get_drive_service/classify_google_error throughout, so this
  slice's prerequisites are satisfied.
- Real call sites (grep -n "google_drive\." app/packages/incident_draft/adapters/google_docs.py):
  only 2 -- _copy_source_document:272 (create_file_from_template) and _source_name_and_folder:1245
  (get_file_by_id). find_files_by_name is NOT called anywhere under app/packages/incident_draft
  (AC#3 corrected on the task itself, see comment).
- Neither call site has any try/except today; failures are inferred from return shape
  (isinstance/falsy checks) and logged via logger.warning. Consequence: an HttpError raised deep in
  google_drive.create_file_from_template/get_file_by_id (both funnel through
  execute_google_api_request, which classifies+logs+re-raises) propagates UNCAUGHT out of
  _copy_source_document/_source_name_and_folder today. write_draft_document's own docstring says
  "Returns None on any failure" -- currently false for this failure mode; this task makes it true.
  This is a deliberate reliability improvement (crash -> graceful degrade), called out below as the
  one real behavior change, not a regression.
- get_file_by_id (app/integrations/google_workspace/google_drive.py:136-144) has exactly one
  production caller repo-wide (the adapter) -- confirmed via grep for "get_file_by_id" across
  app/**/*.py. Safe to delete once step 1 lands.
- create_file_from_template (google_drive.py:86-97) keeps one production caller after this task:
  app/modules/incident/incident_document.py:29 (legacy, no adapter tier) -- stays, per AC#3.
- client.py already exposes get_drive_service(scopes, delegated_user_email) -> DriveResource
  (stub-typed under TYPE_CHECKING) and classify_google_error(exc) -> (OperationStatus, str|None,
  int|None), raising unmapped exceptions. google_drive.py's own DRIVE_SCOPES constant
  (["https://www.googleapis.com/auth/drive"]) is the scope list to reuse -- do not duplicate the
  literal.
- Precedent for "caller builds Resource + owns try/except+classify" already exists at
  infrastructure/directory/google.py::GoogleDirectoryProvider._call (try/except HttpError ->
  classify_google_error -> OperationResult). This adapter's failure contract is different (None /
  tuple-with-fallback, not OperationResult) -- mirrored inline rather than reusing that helper,
  consistent with TASK-25.1.6.6's identical Docs-side design note ("new business logic, not a
  mechanical rewire").

ORDERED STEPS

1. app/packages/incident_draft/adapters/google_docs.py imports (lines 20, 25):
   - Extend `from typing import Any` -> `from typing import TYPE_CHECKING, Any, cast`.
   - Extend `from integrations.google_workspace import google_docs, google_drive` -> add
     `client as google_workspace_client` to the same import.
   - Add `from googleapiclient.errors import HttpError`.
   - Add a `TYPE_CHECKING` block importing `File` from `googleapiclient._apis.drive.v3` (mirrors
     google_drive.py's own pattern) for the `cast("File", ...)` body literal.

2. Repoint `_copy_source_document` (line 270-277). Build
   `service = google_workspace_client.get_drive_service(scopes=google_drive.DRIVE_SCOPES)`, call
   `service.files().copy(fileId=source_document_id, body=cast("File", {"name": draft_title,
   "parents": [folder]}), supportsAllDrives=True, fields="id").execute()` inside
   `try/except HttpError as exc`. On HttpError: `status, error_code, retry_after =
   google_workspace_client.classify_google_error(exc)`, log
   `incident_draft_copy_failed` with `source_document_id`, `status=status.value`, `error_code`,
   `retry_after`, return `None`. Unmapped statuses propagate raw (classify_google_error's own
   `raise exc` -- do not add a second except clause). Keep the existing
   "no id in response -> incident_draft_copy_failed + return None" branch as-is below it.

3. Repoint `_source_name_and_folder` (line 1239-1256). Build the same
   `get_drive_service(scopes=google_drive.DRIVE_SCOPES)` Resource, call
   `service.files().get(fileId=document_id, fields="id, name, parents",
   supportsAllDrives=True).execute()` inside `try/except HttpError as exc`. On HttpError: classify,
   log a NEW event `incident_draft_metadata_lookup_failed` (distinct from the pre-existing
   `incident_draft_parent_folder_not_found`, which fires when the lookup succeeds but the file has
   no parents) with `document_id`, `status.value`, `error_code`, `retry_after`, and set
   `metadata = None` so the existing `isinstance(metadata, dict)` / fallback-to-
   `get_google_resources_config().incident_folder_id` logic runs unchanged.

4. Delete `get_file_by_id` from app/integrations/google_workspace/google_drive.py (lines 136-144).

5. app/tests/integrations/google_workspace/test_google_drive.py: remove `google_drive.get_file_by_id`
   from the `functions` tuple in `test_module_hardcodes_no_field_projection` (~line 62); delete
   `test_get_file_by_id_calls_files_get` and `test_get_file_by_id_propagates_http_error`
   (~lines 190-219, the whole "get_file_by_id" section).

6. app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py -- mock boundary rework
   (dominates this PR's diff, per the task's own SIZE WARNING; 40 blocks patch `_DRIVE`, 23 of them
   also set `create_file_from_template`/`get_file_by_id` return values directly):
   a. Add `_CLIENT = "packages.incident_draft.adapters.google_docs.google_workspace_client"`
      alongside the existing `_DOCS`/`_DRIVE` constants.
   b. Add a local `_http_error(status: int) -> HttpError` helper (same FakeResp-dict shape already
      duplicated per-file in test_google_drive.py / test_google_directory.py / etc. -- this repo's
      established convention is a local copy per test file, not a shared fixture; do not centralize
      it here).
   c. Add ONE shared helper, e.g.
      `_drive_resource_fake(*, copy_response=None, copy_error=None, get_response=None,
      get_error=None) -> MagicMock`, building a MagicMock DriveResource whose
      `.files().copy(...).execute()` / `.files().get(...).execute()` return the given value or raise
      the given error. This is the exact helper TASK-25.1.6.6 is told (its own comment thread) to
      reuse for the Docs half -- keep its name and kwarg shape stable once written.
   d. Update the shared `_write(mock_docs, mock_drive, drafts, *, existing=False, fields=())` helper
      to take a new `mock_client` parameter and set
      `mock_client.get_drive_service.return_value = _drive_resource_fake(copy_response={"id":
      "NEW1"}, get_response={"name": "testing draft functionality", "parents": ["FOLDER1"]})` as its
      default, dropping the two lines that today set `mock_drive.create_file_from_template.
      return_value` / `mock_drive.get_file_by_id.return_value`. Leave the `mock_drive.
      find_files_by_name.return_value = (...)` line untouched (still valid, unrelated to this
      change).
   e. At every `with patch(_DOCS) as mock_docs, patch(_DRIVE) as mock_drive:` block, add
      `, patch(_CLIENT) as mock_client` and thread `mock_client` into `_write(...)` calls. For the
      ~23 blocks that set `create_file_from_template`/`get_file_by_id` return values manually instead
      of via `_write`, replace those two lines with one
      `mock_client.get_drive_service.return_value = _drive_resource_fake(copy_response=...,
      get_response=...)` call.
   f. Rewrite the handful of assertions that read the old mock's call shape directly (not just
      renames -- the new call is keyword-based against `.files().copy`/`.files().get`, not the old
      vendor function's positional signature):
      - `name, folder, template = mock_drive.create_file_from_template.call_args.args` (~line 185) ->
        read `mock_client.get_drive_service.return_value.files.return_value.copy.call_args.kwargs`
        (`fileId`, `body["name"]`, `body["parents"][0]`).
      - `mock_drive.create_file_from_template.assert_called_once()` / `.call_count` (~lines 270, 1566)
        -> `...files.return_value.copy.assert_called_once()` / `.call_count`.
      - `mock_drive.get_file_by_id.call_count` (~line 1565) and
        `mock_drive.get_file_by_id.call_args.args[0]` (~line 1614) ->
        `...files.return_value.get.call_count` / `.call_args.kwargs["fileId"]`.
      - `name = mock_drive.create_file_from_template.call_args.args[0]` (~line 281) -> the
        equivalent `.kwargs["body"]["name"]`.

7. Add two new tests exercising the classification paths added in steps 2-3 (behavior-only
   assertions, matching this file's existing house style -- no test here uses caplog/
   structlog.testing.capture_logs, so don't introduce that pattern solely for these two cases):
   - `test_copy_source_document_http_error_returns_none`: `_drive_resource_fake(copy_error=
     _http_error(503))`; call `write_draft_document`; assert result is `None` (the copy-failed
     branch fires, no Docs calls happen after it).
   - `test_source_name_and_folder_http_error_falls_back_to_configured_folder`: `_drive_resource_fake(
     get_error=_http_error(404), copy_response={"id": "NEW1"})`; patch
     `packages.incident_draft.adapters.google_docs.get_google_resources_config` to return a stub
     with a known `incident_folder_id`; call `write_draft_document`; assert the copy request's
     `body["parents"] == [<that fallback id>]` (this is also the FIRST test anywhere covering the
     fallback-folder branch at all -- it previously had zero coverage even for the pre-existing
     "no parents in response" case).

8. Land the AC#5 obligation: once merged, add a `--comment` to TASK-25.1.6 (its 2026-09-02 13:30
   comment already names exactly this and asks for it) confirming these two call sites are
   discharged from its outstanding inventory.

AC TRACEABILITY
- AC#1 -> steps 1-3; tests: step 6's reworked existing assertions (call-shape now reads
  get_drive_service/files().copy()/files().get()) + step 7's two new tests exercise the try/except+
  classify path directly.
- AC#2 -> step 4; test: step 5's deletions plus confirming no remaining `get_file_by_id` reference
  anywhere (grep, not a runtime test).
- AC#3 -> step 2's "leave create_file_from_template" (no change to that function) + the AC's own
  corrected text (no find_files_by_name call exists or is added) -- verified by leaving
  test_the_existing_draft_lookup_is_gone unmodified (still asserts `mock_drive.find_files_by_name.
  assert_not_called()`).
- AC#4 -> step 6 (shared `_drive_resource_fake` helper, full mock-boundary rework, all existing
  assertions preserved via 6f's rewrites) + step 7 (new classification tests).
- AC#5 -> step 8.

TEST MATRIX
- Happy path: existing `test_copies_the_source_report_rather_than_building_a_blank_doc`,
  `test_writing_a_draft_makes_the_minimum_calls`, and the rest of `TestWriteDraftDocument`/
  `TestRoundTripCount`/`TestReportIsReadOnly` -- all pass unchanged in behavior, rewired onto the new
  fake per step 6.
- Boundary (pre-existing, untouched by this task): copy response missing "id" ->
  `incident_draft_copy_failed` + None (already exercised implicitly by nothing today -- flagged as
  an assumption below, not created new here since it's out of this task's literal scope).
- Failure/new (step 7): Drive copy raises HttpError -> None, no Docs calls; Drive metadata-get raises
  HttpError -> falls back to `get_google_resources_config().incident_folder_id`, draft copy still
  proceeds using the fallback folder.
- Vendor-level (test_google_drive.py, step 5): get_file_by_id's own success/HttpError-propagation
  tests are deleted, not replaced -- their scenario (HttpError during a Drive get) is now covered at
  the point it's actually handled (the adapter, step 7), so there is no net coverage loss.

ASSUMPTIONS AND DOUBTS
- The pre-existing "copy response has no id" and "metadata succeeded but has no parents" warning
  branches have ZERO test coverage today (grep for `incident_draft_copy_failed` /
  `incident_draft_parent_folder_not_found` in the test file returns nothing) -- this predates this
  task and is not required by any of its ACs; not fixed here to avoid scope creep, but worth a
  follow-up note since step 7 adds the sibling HttpError tests right next to these permanently-
  uncovered branches. Verify by re-running the same grep after this task lands to confirm the gap is
  still open, not silently assumed closed.
- New tests assert behavior only (return value / request body), not log field values, to match this
  file's existing style (no caplog/capture_logs usage anywhere in it). If a reviewer wants the
  classification fields (status/error_code/retry_after) asserted directly, that requires adding
  structlog.testing.capture_logs to this file for the first time -- flagged as a judgment call, not
  decided unilaterally.
- classify_google_error re-raises exceptions with unmapped HTTP statuses (anything outside
  404/401/403/429/500/502/503/504) -- both new except blocks let that propagate rather than adding a
  second catch-all, consistent with the sprint-wide "unmapped SDK errors propagate raw" decision
  (TASK-23.2, human-approved 2026-08-31). Not re-litigated here.

BLAST RADIUS AND ROLLBACK
- Single subsystem (Google Drive integration + its one adapter), 2 production files + 2 test files
  touched. Production diff is small (~40-50 LOC changed across the two repointed functions + a
  10-line deletion in google_drive.py) -- well under the gate; test diff is larger but mechanical
  (signature-preserving mock-boundary swap), matching the already-approved TASK-25.1.6.6 sibling's
  identical shape. No decomposition needed.
- The one real behavior change: HttpErrors raised during the copy or metadata-lookup Drive calls no
  longer propagate uncaught out of write_draft_document -- they now degrade gracefully (return None,
  or fall back to the configured incident folder). This is strictly a reliability improvement
  (matches the function's own pre-existing "returns None on any failure" docstring, which was
  previously inaccurate for this path) and is single-`git revert`-safe: reverting restores the prior
  propagate-uncaught behavior with no data/schema/deploy ordering implications.
- No terraform/CI/settings changes. No migration ordering constraints -- this can land independently
  of every other TASK-25.1.6.* sibling except its own explicit pairing note with TASK-25.1.6.6 (which
  depends on this task only to reuse its test helper, not for correctness).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-02 15:06
---
PAIRS WITH TASK-25.1.6.6 (created 2026-09-02). This task repoints packages/incident_draft/adapters/google_docs.py's two DRIVE call sites onto get_drive_service with an inline try/except; TASK-25.1.6.6 does the same for that adapter's DOCS call sites (google_docs.get_document / batch_update). Together they make this file the first fully compliant Google boundary in the repo, per decisions/outbound-clients.md.

Leave behind a SHARED, REUSABLE Resource-fake helper when reworking app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py (1704 lines, 135 mock_drive references). TASK-25.1.6.6 is explicitly instructed to reuse it rather than reinvent the mock chain, so the shape you choose here determines whether that follow-up is cheap or expensive.
---

created: 2026-09-02 16:03
---
AC#3 corrected 2026-09-02 (task-planner): the task's own description claims the adapter 'also calls google_drive.find_files_by_name, which builds a Drive q-DSL query and is genuine domain logic - that call stays on the vendor module.' Fresh grep (grep -n 'google_drive\.' app/packages/incident_draft/adapters/google_docs.py) shows exactly 2 call sites -- create_file_from_template:272 and get_file_by_id:1245 -- and zero calls to find_files_by_name anywhere under app/packages/incident_draft. The test file's mock_drive.find_files_by_name.return_value / .assert_not_called() setups are real and intentional (test_the_existing_draft_lookup_is_gone asserts it is NEVER called -- a deliberate regression guard for the decision documented in _copy_source_document's docstring: every run copies fresh rather than searching Drive for a prior draft), so those lines are untouched by this task, not dead scaffolding to delete. AC#3 reworded to state the accurate fact (adapter does not call find_files_by_name) instead of the false 'still calls' premise. Does not change scope: create_file_from_template still stays in google_drive.py for modules/incident/incident_document.py.
---
<!-- COMMENTS:END -->
