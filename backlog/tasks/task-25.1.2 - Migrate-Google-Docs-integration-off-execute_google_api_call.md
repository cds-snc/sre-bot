---
id: TASK-25.1.2
title: Migrate Google Docs integration off execute_google_api_call
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-31 18:32'
updated_date: '2026-09-01 17:29'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_docs.py
parent_task_id: TASK-25.1
priority: high
ordinal: 113000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.1. Migrate integrations/google_workspace/google_docs.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (DocsResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Docs-specific HttpError families beyond what TASK-22.4/25.1.1 established). Production consumers (grep-confirmed 2026-07-31): modules/incident/incident_document.py, modules/incident/incident_status.py, modules/incident/incident_conversation.py, modules/incident/information_update.py (Docs-related calls only in each file; their Drive-related calls belong to the sibling Drive slice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/google_docs.py no longer calls execute_google_api_call; routes through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [x] #2 The 5 identified consumer files (app/modules/incident/{incident_document,incident_status,incident_conversation,information_update}.py and app/packages/incident_draft/adapters/google_docs.py) behave identically for their Docs-related calls (existing tests pass, behavior-neutral)
- [x] #3 classify_google_error gains any Docs-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEPS

1. app/integrations/google_workspace/client.py: add get_docs_service(scopes, delegated_user_email=None) -> DocsResource (build('docs','v1',...)), mirroring get_calendar_service/get_meet_service exactly (delegates to the existing private _build_service helper, cast to the stub type). Add `from googleapiclient._apis.docs.v1 import DocsResource` under the existing `if TYPE_CHECKING:` block (stub confirmed present at googleapiclient-stubs/_apis/docs/v1, class `DocsResource` with `.documents().create(body: Document)`/`.batchUpdate(documentId, body: BatchUpdateDocumentRequest)`/`.get(documentId)`). Reuse the existing `execute_google_api_request` and `classify_google_error` as-is (no client.py behavior change beyond the new factory) — continuing the pattern TASK-25.1.1 established and explicitly built for reuse by this slice. Do not add new classify_google_error mappings speculatively (mirrors TASK-25.1.1 Step 1's resolution); only add one if a failure-path test below surfaces an unmapped status that needs it, cited with the observed status.

2. app/integrations/google_workspace/google_docs.py: convert create, batch_update, get_document off execute_google_api_call, mirroring google_calendar.py/meet.py's exact shape:
   - Add `from typing import TYPE_CHECKING, cast` and `from integrations.google_workspace import client as google_service_client`; remove `from integrations.google_workspace import google_service` and the `handle_google_api_errors = google_service.handle_google_api_errors` re-export (nothing else in this file uses google_service — extract_google_doc_id is pure regex, no API dependency).
   - Add `if TYPE_CHECKING: from googleapiclient._apis.docs.v1 import BatchUpdateDocumentRequest, Document  # pyright: ignore[reportMissingModuleSource]`.
   - Add a module-level `DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]` (mirrors meet.py's MEET_SCOPES / google_calendar.py's CALENDAR_SCOPES convention).
   - create(title, **kwargs): pop delegated_user_email from kwargs; service = google_service_client.get_docs_service(scopes=DOCS_SCOPES, delegated_user_email=delegated_user_email); body = cast("Document", {"title": title}); return google_service_client.execute_google_api_request(service.documents().create(body=body)).
   - batch_update(document_id, requests, **kwargs): same delegated_user_email extraction; body = cast("BatchUpdateDocumentRequest", {"requests": requests}); return google_service_client.execute_google_api_request(service.documents().batchUpdate(documentId=document_id, body=body)).
   - get_document(document_id, **kwargs): same extraction; return google_service_client.execute_google_api_request(service.documents().get(documentId=document_id)).
   - Remove the now-unused `@handle_google_api_errors` decorators; keep extract_google_doc_id and its docstring/logic completely untouched.
   - google_docs.py's module-level create/batch_update/get_document functions are DELIBERATELY kept as the public API (not deleted or reduced to thin re-exports) — they remain the real call target for all 4 legacy modules/incident/*.py consumers, and for packages/incident_draft/adapters/google_docs.py pending its own future migration (see doubt (e) below / TASK-25.1.6).

3. Prune app/bin/baselines/sdk_typing_antipatterns.txt's `integrations/google_workspace/google_docs.py` entry (mirrors TASK-25.1.1 Step 8's precedent; header states removals are always safe).

4. Rework app/tests/integrations/google_workspace/test_google_docs.py: the 3 tests patching `google_docs.google_service.execute_google_api_call` are rebuilt to patch `google_docs.google_service_client.get_docs_service` returning a MagicMock service, with `.documents().create(body=...).execute()` / `.documents().batchUpdate(documentId=...,body=...).execute()` / `.documents().get(documentId=...).execute()` set to return the same fixture dicts used today. Preserve every existing assertion on returned document/body shape unchanged — only the mock's construction/call-shape changes (same mechanical pattern as TASK-25.1.1 Step 5 for test_google_calendar.py). Add one new failure-path test per function (HttpError propagates unchanged via execute_google_api_request) to close the gap the current file has (today's tests only cover the happy path).

5. Extend app/tests/unit/integrations/google_workspace/test_client.py: add `("get_docs_service", "docs", "v1", "https://www.googleapis.com/auth/documents")` to the existing `test_service_factories_build_with_static_discovery_and_no_cache` / `test_service_factories_use_explicit_delegated_user_email` parametrizations (both already parametrized over factory_name — this is a one-line addition per test, no new test function needed).

6. Confirm the two currently-untouched Docs consumers remain green with zero edits (both mock at the `google_docs` module-function boundary, unaffected by internal rewiring):
   - app/tests/modules/incident/test_incident_document.py, test_incident_status.py, test_incident_conversation.py, test_information_update.py (patch `modules.incident.<file>.google_docs` wholesale).
   - app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py (patches `packages.incident_draft.adapters.google_docs.google_docs` wholesale) — app/packages/incident_draft/adapters/google_docs.py is a 5th real production consumer of google_docs.get_document/batch_update (confirmed via repo-wide `import google_docs` grep, 2026-09-01) that was never listed in this task's own Description/AC#2 nor in TASK-25.1's parent consumer inventory; no code change needed there since it calls the same public functions with the same signatures/return shapes, but it must be named explicitly as in-scope-for-behavior-neutrality, not silently swept in. See doubt (e): migrating this adapter onto get_docs_service directly is explicitly deferred, not silently left legacy by oversight.

7. Re-run repo-wide checks: grep for execute_google_api_call in google_docs.py (expect zero); grep for `import google_docs` repo-wide to reconfirm exactly 5 production consumers before/after; bin/check_sdk_typing.py; bin/check_deprecated_infra_client_imports.py; bin/generate_client_usage_matrix.sh.

AC-TO-STEP-TO-TEST
- AC#1 (google_docs.py routes through factory + classify_google_error, raising/classifying per outbound-clients.md) -> Steps 1-2. Verified by: grep for execute_google_api_call in google_docs.py returns zero; mypy resolves get_docs_service's stub-typed return and the chained .documents().create()/.batchUpdate()/.get() calls with no Any leakage; Step 4 tests.
- AC#2 (the 5 identified consumer files behave identically) -> Steps 2 (internals only, public function signatures/return shapes unchanged) + Step 6 (existing test suites for all 5 consumers run green with zero edits).
- AC#3 (classify_google_error gains any Docs-specific mapped families with unit coverage) -> Step 1's explicit decision not to speculatively extend it, revisited only if Step 4's new failure-path tests surface an unmapped status that needs a family, in which case add it with justification and coverage under tests/unit/integrations/google_workspace/.

TEST MATRIX
Happy path: create/batch_update/get_document each return the same shape as today given a mocked successful Resource chain. Delegated-email: default-to-SRE_BOT_EMAIL and explicit-override cases for all three functions (mirrors the existing get_calendar_service/get_meet_service coverage pattern — new for Docs, since today's dispatcher-based tests never asserted delegation explicitly). Error propagation: HttpError with a classified status (e.g. 404 on get_document, 429 on batch_update) logs and re-raises unchanged; an unmapped HttpError status and a non-HttpError exception both propagate via classify_google_error's own raise, unchanged exception identity (new tests, closing today's happy-path-only gap). Construction: get_docs_service build() call assertions (service/version/cache_discovery=False/static_discovery=True) via the existing parametrized factory tests. Regression: full existing app/tests/modules/incident/{test_incident_document.py,test_incident_status.py,test_incident_conversation.py,test_information_update.py} and app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py suites green with zero edits (proves AC#2 module-boundary behavior neutrality across all 5 real consumers). Commands: cd app && uv run pytest tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/incident tests/unit/packages/incident_draft -v; then make test (project's CI split); then uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; then uv run ruff check .; then bin/check_sdk_typing.py, bin/check_deprecated_infra_client_imports.py, bin/generate_client_usage_matrix.sh.

ASSUMPTIONS AND DOUBTS (verify at impl)
(a) execute_google_api_request's long-term home (client.py vs. per-call-site) is intentionally deferred to TASK-25.1.6, not re-litigated here — see the correction recorded on TASK-25.1.6 this session (2026-09-01): that task's framing as a symmetric "inline vs. formalize-as-permanent" decision was inaccurate. decisions/outbound-clients.md already decided the target shape (clients raise, adapters classify, one tier); execute_google_api_request classifying inside client.py is a real, currently-necessary deviation, not an open question, tolerated only because today's actual Docs/Calendar/Meet call sites (4 legacy app/modules/incident/*.py files with no adapter tier at all, plus packages/incident_draft/adapters/google_docs.py — a real packages/<feature>/adapters/ file that itself performs no try/except/classify today) have nowhere compliant to inline the try/except into without a separate migration. This slice continues using the shared helper for consistency with TASK-25.1.1 and because it is behavior-preserving; it does not attempt to build a real adapter boundary for modules/incident's Docs usage, which is out of this slice's scope.
(b) Whether any Docs HttpError status needs a new classify_google_error family beyond the existing 404/401/403/429/5xx table — no evidence found in current code/tests (no try/except around any google_docs call anywhere in the 5 consumers); only add if a failure-path test in Step 4 surfaces one, with the observed status cited in the commit.
(c) create()'s **kwargs today silently drops any stray unsupported kwarg via the old dispatcher's docstring-based filtering; the new direct-call design only extracts delegated_user_email and would raise a TypeError on any other stray kwarg reaching documents().create(). Zero production call sites pass anything beyond delegated_user_email (grep-confirmed; create() itself has zero production call sites at all, test-only) — accepted, not blocking, same reasoning as TASK-25.1.1's assumption (c).
(d) client.py's existing classify_google_error retains its `except TypeError, ValueError:` bare-tuple except clause (valid under this repo's pinned Python 3.14 grammar) — pre-existing from TASK-22.4, out of this slice's scope, not touched.
(e) HUMAN-CONFIRMED DECISION (2026-09-01): packages/incident_draft/adapters/google_docs.py post-dates the original TASK-25.1 consumer inventory (a colleague built the incident-draft feature package after this task family was first scoped) and, being a real packages/<feature>/adapters/ file, ideally should call get_docs_service directly + do its own inline try/except+classify_google_error — the proper end-state shape — rather than depending on google_docs.py's module-level get_document/batch_update passthrough, which is a legacy two-tier stack (vendor module classifies via execute_google_api_request, adapter just calls it again). That migration is explicitly OUT OF SCOPE for this slice: its test file alone is 1704 lines with 44 separate `patch("packages.incident_draft.adapters.google_docs.google_docs")` call sites keyed to the current mock boundary, and the adapter today has ZERO try/except around its google_docs calls (only an isinstance shape check) — giving it real classify-based error handling is new business logic (deciding OperationStatus-to-None/[]-on-failure mapping for read_sections/write_draft_document), not a mechanical rewire, and would blow well past a reviewable single PR alongside this slice's own client.py/google_docs.py work. Folded into TASK-25.1.6's reconciliation scope instead (that task's AC#2 already covers "every call site already in a real packages/<feature>/adapters/ file"; a comment there now names this file+decision explicitly).

BLAST RADIUS / ROLLBACK
Contained to integrations/google_workspace/{client.py,google_docs.py} (edits) and their test files (test_google_docs.py reworked, test_client.py extended). No infrastructure/, packages/, terraform/, or CI changes — packages/incident_draft/adapters/google_docs.py is read-only-verified (its own test suite proves it), not edited; its migration onto get_docs_service directly is deliberately deferred to TASK-25.1.6 (see doubt (e)), not an oversight. modules/incident/{incident_document,incident_status,incident_conversation,information_update}.py are untouched (consumers of the same public function signatures). Single git revert restores the execute_google_api_call-based implementation. No ordering constraint against sibling slices TASK-25.1.3/.4/.5 (each touches disjoint files); google_service.py itself stays alive for those siblings' remaining consumers.

SIZE GATE: fits comfortably in one PR, smaller than the already-approved TASK-25.1.1 precedent. Production diff: 2 files (client.py ~15-20 new LOC for 1 factory; google_docs.py ~30-40 LOC net changed, no new file). Test diff: 1 file reworked + extended with new failure-path cases (test_google_docs.py), 1 file extended with 2 new parametrize entries (test_client.py). Single subsystem (Google Workspace vendor client), no cross-cutting refactor, no packages/ changes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-01.

Production changes:
- integrations/google_workspace/client.py: added get_docs_service(scopes, delegated_user_email=None) -> DocsResource (build('docs','v1')) + DocsResource TYPE_CHECKING import; module docstring rewritten (was Directory-only framing, now describes the generic Google Workspace vendor client covering Directory/Calendar/Meet/Docs factories + shared classification). No behavior change to classify_google_error / execute_google_api_request.
- integrations/google_workspace/google_docs.py: create/batch_update/get_document rewired off google_service.execute_google_api_call onto get_docs_service + execute_google_api_request, with DOCS_SCOPES module constant and cast('Document')/cast('BatchUpdateDocumentRequest') bodies. Removed the google_service import, the handle_google_api_errors re-export and its decorators. extract_google_doc_id untouched. Results bound to 'result: dict' before return (mirrors meet.py) to avoid no-any-return leakage from execute_google_api_request's Any.
- bin/baselines/sdk_typing_antipatterns.txt: pruned the google_docs.py entry (15 baselined files remain).

AC#3: no new classify_google_error family was needed. Failure-path tests exercised 429/404 (already mapped), 418 (unmapped) and a non-HttpError; all propagate with unchanged exception identity through the existing table, so no speculative mapping was added (plan Step 1 / doubt (b) resolution). Coverage for those paths lives in tests/integrations/google_workspace/test_google_docs.py plus the pre-existing tests/unit/integrations/google_workspace/test_client.py classification tests.

Test evidence:
- tests/integrations/google_workspace/test_google_docs.py reworked onto a docs_client fixture patching client.get_docs_service: happy path x3 (same return shapes + call kwargs asserted), delegated_user_email default(None)/explicit-override x3, error propagation x5 (429 create, 429 batch_update, 404/418/RuntimeError get_document), plus a guard that google_docs no longer exposes google_service. extract_google_doc_id tests unchanged.
- tests/unit/integrations/google_workspace/test_client.py: get_docs_service added to both factory parametrizations (docs/v1/auth-documents; cache_discovery=False, static_discovery=True, delegation).
- Targeted run green: tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/incident tests/unit/packages/incident_draft -> 645 passed. All 5 consumers (modules/incident/{incident_document,incident_status,incident_conversation,information_update}.py and packages/incident_draft/adapters/google_docs.py) green with ZERO edits, proving AC#2 behavior neutrality.
- mypy: 99 errors / 34 files, all pre-existing elsewhere; zero in client.py or google_docs.py (an initial 3 no-any-return errors from the rewire were fixed, not baselined).
- ruff check: clean. bin/check_sdk_typing.py: OK. bin/check_deprecated_infra_client_imports.py: OK. grep for execute_google_api_call in google_docs.py: zero hits.
- User confirmed a full local 'make test' run green after these changes.

Deviations from plan: none material. Plan Step 4 said to patch google_docs.google_service_client.get_docs_service; tests patch client.get_docs_service instead (same object, matches the existing test_google_calendar.py calendar_client fixture precedent).

Deferred / left for human verification:
- bin/generate_client_usage_matrix.sh was not re-run (plan Step 7); the two python guard checks were.
- packages/incident_draft/adapters/google_docs.py deliberately NOT migrated onto get_docs_service (plan doubt (e) / TASK-25.1.6).
- TASK-25.1.6 still needs its call-site inventory updated with this slice's 3 new execute_google_api_request call sites in google_docs.py (per the 2026-09-01 tracking comment on this task).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:34
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. When implementing this slice, if google_docs.py's migrated call sites use execute_google_api_request (or you introduce an equivalent), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's.
---

created: 2026-09-01 16:54
---
TASK-25.1.6 corrected 2026-09-01 (task-planner): its 'inline vs. formalize-as-permanent' framing was inaccurate (user-flagged) — decisions/outbound-clients.md already decided the target shape, so reusing execute_google_api_request here is a knowingly-tolerated temporary deviation pending a real adapter-tier migration for app/modules/incident and app/packages/incident_draft/adapters/google_docs.py, not an open architectural vote. This slice's plan reuses execute_google_api_request per TASK-25.1.1's precedent (behavior-preserving, consistent), not as an endorsement of keeping it permanently.
---
<!-- COMMENTS:END -->
