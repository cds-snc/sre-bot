---
id: TASK-25.1.6.6
title: Inline Docs construction and classification in packages incident_draft adapter
status: To Do
assignee: []
created_date: '2026-09-02 15:01'
updated_date: '2026-09-08 15:00'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.5.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 137000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Docs counterpart of TASK-25.1.5.1 (which does the same for that adapter's two Drive call sites). Together they make app/packages/incident_draft/adapters/google_docs.py the first fully compliant Google boundary in the repo.

app/packages/incident_draft/adapters/google_docs.py is a real packages/<feature>/adapters/ file per decisions/feature-packages.md - i.e. it is exactly where decisions/outbound-clients.md says the boundary belongs ("the adapter is the boundary"). Today it calls integrations.google_workspace.google_docs.get_document / batch_update - module-level passthroughs that add nothing over the SDK - and performs ZERO try/except of its own, relying on the vendor package's execute_google_api_request to classify. That is the deviation TASK-25.1.6 exists to remove.

SCOPE: repoint those Docs call sites onto integrations.google_workspace.client.get_docs_service(scopes=..., delegated_user_email=...), call service.documents().get(...) / .batchUpdate(...) directly against the stub-typed DocsResource, and give the adapter its own try/except + classify_google_error. Translate responses into the adapter's own typed shapes rather than passing raw dicts inward (decisions/sdk-typing.md item 3).

REAL DESIGN WORK, NOT A MECHANICAL REWIRE (flagged on TASK-25.1.6, 2026-09-01): the adapter's read_sections / write_draft_document currently express failure as None / [] returns. Deciding how classify_google_error's OperationStatus maps onto those - or whether they should return OperationResult instead - is new business logic and is the substance of this task.

SIZE WARNING: app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py is 1704 lines with 44 patch(...) sites keyed to the current google_docs module boundary. TASK-25.1.5.1 already splits that boundary once for Drive and is expected to leave a shared Resource-fake helper behind; reuse it rather than reinventing the chain per test. Expect the test rework, not the production change, to dominate this PR.

AFTER THIS TASK: integrations/google_workspace/google_docs.py::get_document and batch_update have one remaining consumer group - the legacy modules/incident/* files owned by the incident Docs adapter task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident_draft/adapters/google_docs.py builds its Docs calls from integrations.google_workspace.client.get_docs_service and calls documents().get / documents().batchUpdate directly on the stub-typed DocsResource; it no longer imports integrations.google_workspace.google_docs
- [ ] #2 The adapter wraps those calls in its own try/except + classify_google_error and no longer depends on execute_google_api_request for any call site
- [ ] #3 The mapping from classify_google_error's OperationStatus onto the adapter's existing None/[] failure contract (read_sections, write_draft_document) is decided explicitly, documented in the notes, and covered by tests for each mapped status
- [ ] #4 Raw Docs response dicts do not cross out of the adapter; responses are translated into the adapter's own typed shapes
- [ ] #5 test_incident_draft_adapter.py is reworked onto the split mock boundary reusing TASK-25.1.5.1's shared Resource fake; every existing behavioural assertion is preserved or has a documented equivalent
- [ ] #6 TASK-25.1.6's call-site inventory is updated to record these Docs sites as discharged, and integrations/google_workspace/google_docs.py's remaining consumers are re-stated
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING FACTS (verified 2026-09-08)

- Adapter: app/packages/incident_draft/adapters/google_docs.py (1354 lines). Exactly 3 call sites
  reference the vendor `google_docs` module: read_sections's get_document (~line 149),
  write_draft_document's post-copy get_document (~line 215), write_draft_document's batch_update
  (~line 225). Confirmed via grep -- no other `google_docs.` reference exists in this file.
- Vendor module app/integrations/google_workspace/google_docs.py is NOT deleted or trimmed by this
  task: get_document/batch_update still have a live production consumer outside this adapter --
  app/modules/incident/incident_document.py (5 call sites: get_document x2 at lines 119/176,
  batch_update x3 at lines 76/112/285), a frozen legacy module per decisions/migration.md rule 1,
  out of scope here and owned by whichever task later builds the incident Docs adapter (per this
  task's own "AFTER THIS TASK" note). google_docs.py::create has ZERO production callers repo-wide
  (grep-verified; only its own vendor test file calls it) -- pre-existing dead code, not touched,
  only recorded in the AC#6 post-merge comment.
- client.py already exposes get_docs_service(scopes, delegated_user_email) -> DocsResource
  (stub-typed under TYPE_CHECKING) and classify_google_error(exc) -> (OperationStatus, error_code,
  retry_after) -- the same primitives TASK-25.1.5.1 already used for this adapter's Drive half.
- DESIGN DECISION (AC#3): keep the adapter's existing None/[] failure contract; do NOT introduce
  OperationResult. IncidentDocumentPort (app/packages/incident_draft/service.py:205-219) declares
  read_sections -> list[DocumentSection] (empty on failure) and write_draft_document ->
  DraftWriteResult | None, and draft_incident_document already branches on None/empty-list, not
  OperationResult -- changing the Port would ripple into service.py and no AC asks for that.
  TASK-25.1.5.1's own implementation notes explicitly anticipate this: "This adapter's failure
  contract is different (None/tuple-with-fallback, not OperationResult) -- mirrored inline rather
  than reusing that helper, consistent with TASK-25.1.6.6's identical Docs-side design note." Each
  of the 3 call sites logs classified status/error_code/retry_after and returns the SAME failure
  value ([]/None) the call site already returns today; no second except clause; unmapped statuses
  propagate raw via classify_google_error's own re-raise (not re-litigated, matches TASK-25.1.6's
  sprint-wide convention).
- AC#1 IS STRICTER THAN THE DRIVE PRECEDENT: it says the adapter "no longer imports
  integrations.google_workspace.google_docs" -- full stop, unlike Drive's carve-out (25.1.5.1 kept
  `from integrations.google_workspace import google_drive` solely for the DRIVE_SCOPES constant).
  Read literally, this forbids importing google_docs.DOCS_SCOPES too, so the scope literal
  (["https://www.googleapis.com/auth/documents"]) must be duplicated locally in the adapter as a
  new `_DOCS_SCOPES` constant. Flagged under Assumptions below in case this stricter reading is an
  AC wording accident rather than a deliberate deviation from the Drive carve-out.
- TASK-76 (relocate managed-group policy out of infrastructure/directory into packages/access):
  verified DONE -- all 5 subtasks (76.1-76.5) Status: Done, coordinator awaiting human close-out.
  Its diff touches only app/infrastructure/directory/* and app/packages/access/*; zero references
  to packages/incident_draft or integrations/google_workspace/google_docs.py. CONCLUSION: no impact
  on this task's scope, call sites, or design decisions -- no sibling-task edits needed on that
  account.
- TASK-25.1.6's own comment #17 (2026-09-08) already states the coordinator's execution order with
  this task (.6.6) as the immediate next slice after all Directory-work children landed -- no
  reordering needed, this plan proceeds as the next slice.
- Test file: app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py (1708 lines),
  42 `with patch(_DOCS) as mock_docs:` blocks at lines 100, 113, 222, 280, 297, 310, 323, 332, 343,
  357, 366, 378, 411, 424, 436, 448, 460, 510, 540, 603, 682, 744, 825, 910, 956, 1005, 1073, 1097,
  1114, 1151, 1177, 1201, 1298, 1376, 1482, 1540, 1565, 1580, 1596, 1618, 1648, 1668. It already has
  the `_drive_resource_fake`/`drive_service`/`_copy_request`/`_http_error` helpers TASK-25.1.5.1
  left behind explicitly for this task to reuse (its 2026-09-02 16:38 comment on TASK-25.1.6 names
  them for this exact purpose).

ORDERED STEPS

PRODUCTION -- app/packages/incident_draft/adapters/google_docs.py

1. Imports. Change `from integrations.google_workspace import google_docs, google_drive` to
   `from integrations.google_workspace import google_drive` (drop google_docs entirely). Extend the
   existing `if TYPE_CHECKING:` block (which today only imports `File` from
   googleapiclient._apis.drive.v3) to also import `BatchUpdateDocumentRequest, Document` from
   `googleapiclient._apis.docs.v1`. Add a new module constant near the other private constants:
   `_DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]`, with a one-line comment noting
   it is duplicated from google_docs.DOCS_SCOPES because AC#1 forbids importing that module.

2. Repoint read_sections's get_document call (~line 149). Replace:
     document = google_docs.get_document(document_id)
     if not isinstance(document, dict):
         logger.warning("incident_draft_document_fetch_failed", document_id=document_id)
         return []
   with a `service = google_workspace_client.get_docs_service(scopes=_DOCS_SCOPES)` call, then
   `try: document: Document = service.documents().get(documentId=document_id).execute()` wrapped in
   `except HttpError as exc:` that classifies via `google_workspace_client.classify_google_error(exc)`,
   logs the SAME event name `incident_draft_document_fetch_failed` with
   document_id/status.value/error_code/retry_after, and returns `[]`. Keep the existing
   `if not isinstance(document, dict): ... return []` guard unchanged below it (defensive, matches
   TASK-25.1.5.1's precedent of leaving the pre-existing malformed-response branch in place).

3. Repoint write_draft_document's post-copy get_document call (~line 215) the same way, reusing the
   event name `incident_draft_draft_fetch_failed` (distinct from step 2's event, as today) and
   returning `None` from both the except branch and the unchanged isinstance guard.

4. Repoint write_draft_document's batch_update call (~line 225), REUSING the `service` variable
   built in step 3 (one get_docs_service() call per write_draft_document invocation, not two).
   Build `body = cast("BatchUpdateDocumentRequest", {"requests": requests})`, call
   `service.documents().batchUpdate(documentId=document_id, body=body).execute()` inside
   `try/except HttpError as exc`, classify, log `incident_draft_populate_failed` with
   document_id/status.value/error_code/retry_after, return `None`. Keep the existing
   `if not isinstance(result, dict): ... return None` guard unchanged below it.

TESTS -- app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py

5. Foundation (fixtures/helpers).
   a. Remove the `_DOCS = "packages.incident_draft.adapters.google_docs.google_docs"` constant
      (dead once steps 1-4 land).
   b. Extract the `patch(_CLIENT)` context already used by the `drive_service` fixture into a new
      shared autouse `google_client` fixture; make `drive_service` consume it via a fixture
      dependency instead of patching `_CLIENT` itself (same effective behavior, now shared):
        @pytest.fixture(autouse=True)
        def google_client():
            with patch(_CLIENT) as mock_client:
                yield mock_client

        @pytest.fixture(autouse=True)
        def drive_service(google_client):
            service = _drive_resource_fake(copy_response={"id": "NEW1"},
                get_response={"name": "testing draft functionality", "parents": ["FOLDER1"]})
            google_client.get_drive_service.return_value = service
            return service
   c. Add `_docs_resource_fake(*, get_response=None, get_error=None, batch_response=None,
      batch_error=None) -> MagicMock`, mirroring `_drive_resource_fake`'s shape 1:1 but for
      `service.documents().get(...).execute()` / `service.documents().batchUpdate(...).execute()`.
   d. Add a matching autouse fixture:
        @pytest.fixture(autouse=True)
        def docs_service(google_client):
            service = _docs_resource_fake(get_response=_template_document(), batch_response={})
            google_client.get_docs_service.return_value = service
            return service
      (place it directly below `_template_document`'s definition for readability; Python resolves
      the name at call time so definition order is not a hard requirement).
   e. Add `_batch_requests(docs_service, index=0)` mirroring `_copy_request`:
        def _batch_requests(docs_service, index=0):
            calls = docs_service.documents.return_value.batchUpdate.call_args_list
            return calls[index].kwargs["body"]["requests"] if calls else []

6. Mechanical rewrite: eliminate all 42 `with patch(_DOCS) as mock_docs:` blocks listed in Grounding
   Facts. Each enclosing test method/helper gains a `docs_service` parameter (already available via
   the autouse fixture -- no explicit `with` needed); dedent the block body one level; translate
   every `mock_docs.*` access per this table:
     mock_docs.get_document.return_value = X
       -> docs_service.documents.return_value.get.return_value.execute.return_value = X
     mock_docs.batch_update.return_value = Y
       -> docs_service.documents.return_value.batchUpdate.return_value.execute.return_value = Y
     mock_docs.batch_update.side_effect = [A, B]                              (line ~512)
       -> docs_service.documents.return_value.batchUpdate.return_value.execute.side_effect = [A, B]
     mock_docs.batch_update.reset_mock()                                      (line ~1158)
       -> docs_service.documents.return_value.batchUpdate.reset_mock()
     mock_docs.batch_update.call_args_list[0].args[1]
       -> _batch_requests(docs_service)
     mock_docs.batch_update.call_args_list[0].args   (2-tuple unpack, ~line 1648 area)
       -> call = docs_service.documents.return_value.batchUpdate.call_args_list[0]
          document_id, requests = call.kwargs["documentId"], call.kwargs["body"]["requests"]
     {call.args[0] for call in mock_docs.batch_update.call_args_list}         (lines ~369, ~1621)
       -> {call.kwargs["documentId"] for call in docs_service.documents.return_value.batchUpdate.call_args_list}
     mock_docs.batch_update.assert_not_called()                               (lines ~252, 314, 440)
       -> docs_service.documents.return_value.batchUpdate.assert_not_called()
     mock_docs.get_document.call_count / mock_docs.batch_update.call_count    (lines ~1588, 1590)
       -> docs_service.documents.return_value.get.call_count / ...batchUpdate.call_count
     {call.args[0] for call in mock_docs.get_document.call_args_list}         (line ~1628)
       -> {call.kwargs["documentId"] for call in docs_service.documents.return_value.get.call_args_list}

   Named exceptions requiring individual attention (helper functions carrying their own `mock_docs`
   parameter, beyond the plain table above):
     - `_write(mock_docs, drafts, *, fields=())` (~line 186) and every call site (`_write(mock_docs,
       drafts)`): rename the parameter to `docs_service`; its internal
       `mock_docs.get_document.return_value = _template_document()` /
       `mock_docs.batch_update.return_value = {}` lines become redundant with the fixture's own
       defaults -- keep them as explicit within-helper assignments for clarity (translated per the
       table), do not silently drop them.
     - `TestDoubledValueRepair._run(self, document)` (~line 1201) -> `_run(self, docs_service,
       document)`; its 6 call sites gain the parameter.
     - `TestEditsNeverOverlap._requests(self)` (~line 1298) -> `_requests(self, docs_service)`; its
       3 call sites gain the parameter.
     - `TestTemplateNoiseRemoved._run(self, drafts)` (~line 1596) -> `_run(self, docs_service,
       drafts)`; its 2 call sites gain the parameter.
     - `TestEveryPullRequestFormIsLinked._linked_urls(self, content)` (~line 1668) ->
       `_linked_urls(self, docs_service, content)`; its parametrized test and 2 direct callers gain
       the parameter.
     - `test_drive_copy_failure_writes_nothing` (~line 237) and
       `test_metadata_failure_still_copies_into_the_configured_folder` (~line 255): their
       `mock_docs.get_document.return_value` / `mock_docs.batch_update.return_value` lines are DEAD
       once Drive fails first (no Docs call is ever reached) -- DELETE rather than translate; do not
       add a new `assert_not_called()` on Docs here (matches the file's existing style of not
       asserting that for these two tests).
     - `TestReadSections.test_fetch_failure_returns_empty_list` (~line 113): keep this exact
       malformed-response case (`docs_service.documents.return_value.get.return_value.execute.return_value
       = None`) as the boundary test, distinct from step 7's new HttpError tests.

7. New coverage for AC#3 (classification mapping). Add one parametrized test per call site, each
   covering all 3 of classify_google_error's mapped statuses (404->NOT_FOUND, 403->UNAUTHORIZED,
   503->TRANSIENT_ERROR), reusing the existing `_http_error(status)` helper:
     class TestReadSections:
         @pytest.mark.parametrize("status", [404, 403, 503])
         def test_fetch_http_error_returns_empty_list(self, docs_service, status):
             docs_service.documents.return_value.get.return_value.execute.side_effect = _http_error(status)
             assert GoogleDocsIncidentDocument().read_sections("D1") == []

     class TestWriteDraftDocument:
         @pytest.mark.parametrize("status", [404, 403, 503])
         def test_draft_fetch_http_error_returns_none(self, docs_service, status):
             docs_service.documents.return_value.get.return_value.execute.side_effect = _http_error(status)
             drafts = [SectionDraft(heading="Summary", content="x", is_drafted=True)]
             assert GoogleDocsIncidentDocument().write_draft_document("D1", drafts) is None

         @pytest.mark.parametrize("status", [404, 403, 503])
         def test_populate_http_error_returns_none(self, docs_service, status):
             docs_service.documents.return_value.batchUpdate.return_value.execute.side_effect = _http_error(status)
             drafts = [SectionDraft(heading="Summary", content="x", is_drafted=True)]
             assert GoogleDocsIncidentDocument().write_draft_document("D1", drafts) is None
   These exercise the REAL classify_google_error function end-to-end (only get_docs_service/its
   Resource is mocked via the `docs_service` fixture) -- a stronger check than the two pre-existing
   Drive failure tests, which stub `mock_client.classify_google_error.return_value` because `_CLIENT`
   is wholesale-patched there. No caplog/capture_logs, matching this file's existing convention.

8. Validation, scoped then full (per copilot-instructions Validation Policy):
     cd app && uv run mypy packages/incident_draft/adapters/google_docs.py --exclude '(?:^|/)\.venv(?:/|$)'
     cd app && uv run ruff check packages/incident_draft/adapters/google_docs.py tests/unit/packages/incident_draft/test_incident_draft_adapter.py
     cd app && uv run pytest tests/unit/packages/incident_draft/test_incident_draft_adapter.py -q
     cd app && uv run python bin/check_sdk_typing.py   (guardrail unaffected by this task; run anyway)
   then the full gate before calling this task done: mypy ., ruff check ., pytest tests
   --ignore=tests/smoke.

9. POST-MERGE (AC#6): `backlog task edit TASK-25.1.6 --comment "..."` recording that the 3 Docs
   call sites in packages/incident_draft/adapters/google_docs.py are discharged, and restating
   google_docs.py's remaining consumer as app/modules/incident/incident_document.py (get_document
   x2, batch_update x3) plus the pre-existing dead `create()` (test-only caller, unowned).

AC TRACEABILITY
- AC#1 -> steps 1-4; verified by grep for "google_workspace.google_docs" / "import google_docs" in
  the adapter returning zero hits after landing.
- AC#2 -> steps 2-4 (try/except + classify_google_error at all 3 sites, no execute_google_api_request
  dependency remaining); tests: step 6's reworked assertions (call shape now reads
  get_docs_service/documents().get()/batchUpdate()) + step 7's new classification tests.
- AC#3 -> the Grounding Facts design decision (keep None/[] contract) + step 7's 3 parametrized
  tests (9 executions across 3 call sites x 3 mapped statuses) using the real classify_google_error.
- AC#4 -> step 1 (Document/BatchUpdateDocumentRequest stub typing at the SDK boundary) + confirming
  read_sections/write_draft_document already return only DocumentSection/DraftWriteResult dataclasses
  to callers outside the adapter (grep: no external import of anything but GoogleDocsIncidentDocument
  from this module).
- AC#5 -> steps 5-7 (fixture/helper rework covering all 42 patch sites + 4 helper-function
  signature changes), full existing test suite green plus the 9 new failure-path tests.
- AC#6 -> step 9.

TEST MATRIX
- Happy path: all existing TestReadSections/TestWriteDraftDocument/TestDoubledValueRepair/
  TestEditsNeverOverlap/TestTemplateNoiseRemoved/TestRoundTripCount/TestReportIsReadOnly/
  TestEveryPullRequestFormIsLinked tests pass unchanged in behavior, rewired onto `docs_service`.
- Boundary (pre-existing, untouched): test_fetch_failure_returns_empty_list (malformed/non-dict
  response, not an HttpError).
- Failure/new (step 7): documents().get() raises HttpError at read_sections's fetch -> [];
  at write_draft_document's post-copy fetch -> None; documents().batchUpdate() raises HttpError ->
  None; each parametrized over NOT_FOUND/UNAUTHORIZED/TRANSIENT_ERROR-mapped statuses (9 cases).
- Vendor-level (test_google_docs.py): UNCHANGED -- get_document/batch_update/create keep their
  existing tests since the vendor module itself is untouched (still serves
  modules/incident/incident_document.py).

ASSUMPTIONS AND DOUBTS
- Keeping the None/[] failure contract instead of introducing OperationResult is this task's
  load-bearing call (AC#3 explicitly names OperationResult as a considered alternative). Grounded
  in IncidentDocumentPort/draft_incident_document's existing None/empty-list branching and
  TASK-25.1.5.1's own notes anticipating this exact continuation. Flagged for human confirmation
  since AC#3 asks for an explicit decision, not a silent default.
- AC#1's literal wording forces duplicating the Docs scope literal locally rather than reusing
  google_docs.DOCS_SCOPES the way 25.1.5.1 kept importing google_drive solely for DRIVE_SCOPES.
  If this stricter reading is an AC wording accident rather than an intended deviation from the
  Drive precedent, AC#1 needs a `--comment` correction before implementation; proceeding on the
  literal reading otherwise.
- The 3 new classification tests (step 7) exercise the real classify_google_error function rather
  than mocking its return value, unlike the two pre-existing Drive failure tests -- an intentional
  strengthening, not an inconsistency to fix.
- No caplog/structlog.testing.capture_logs introduced, matching this file's existing convention
  (inherited judgment call from TASK-25.1.5.1, not re-litigated here).
- TASK-76 verified fully merged with zero overlap with this task's files -- recorded per the
  request to check for cross-task impact; no action needed.

BLAST RADIUS AND ROLLBACK
- Single subsystem (Google Docs integration + its one adapter). Production diff: 1 file
  (packages/incident_draft/adapters/google_docs.py), ~60-80 LOC changed across 3 call sites plus
  imports/constant -- smaller than TASK-25.1.5.1's Drive counterpart (no vendor-module deletion here,
  since modules/incident/incident_document.py still needs get_document/batch_update). Test diff: 1
  file, large mechanical rewrite (42 patch-block conversions, 4 helper-signature changes, 9 new
  tests) -- consistent with this task's own SIZE WARNING and within the single-PR gate, since the
  gate measures production LOC/files/subsystems and explicitly excludes test LOC.
  Well under the gate; no decomposition needed.
- Real behavior change (same shape as TASK-25.1.5.1): HttpErrors from these 3 Docs calls no longer
  propagate uncaught out of read_sections/write_draft_document -- they now degrade gracefully
  ([]/None), which is what both methods' docstrings already promise but the current
  execute_google_api_request-based path does not actually deliver (it logs and re-raises). Single
  `git revert`-safe: reverting restores the prior propagate-uncaught behavior with no data/schema/
  deploy ordering implications.
- No terraform/CI/settings changes. No ordering constraint against TASK-25.1.6's other open
  children (.7-.11) -- this slice is next in the coordinator's stated execution order (its 2026-09-08
  comment #17) and none of the later slices depend on anything beyond this task's own AC#6
  call-site-inventory update.
<!-- SECTION:PLAN:END -->
