---
id: TASK-25.1.3
title: Migrate Google Sheets integration off execute_google_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:32'
updated_date: '2026-09-01 18:31'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/sheets.py
parent_task_id: TASK-25.1
priority: high
ordinal: 114000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.1. Migrate integrations/google_workspace/sheets.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (SheetsResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Sheets-specific HttpError families, notably the existing non-critical get_sheet 'Unable to parse range' warning handling in google_service.py's handle_google_api_errors decorator - preserve that behavior exactly). Production consumers (grep-confirmed 2026-07-31): modules/incident/incident_folder.py, modules/aws/spending.py, modules/reports/google_groups.py (Sheets-related calls only in each file; their Drive/Directory-related calls belong to sibling slices).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/google_workspace/sheets.py no longer calls execute_google_api_call; routes through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [ ] #2 The 3 identified consumer files behave identically for their Sheets-related calls (existing tests pass, behavior-neutral), including the get_sheet 'Unable to parse range' non-critical warning preserved
- [ ] #3 classify_google_error gains any Sheets-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEPS

1. app/integrations/google_workspace/client.py: add get_sheets_service(scopes, delegated_user_email=None) -> SheetsResource (build('sheets','v4',...)), mirroring get_docs_service/get_calendar_service/get_meet_service exactly (delegates to the existing private _build_service helper, cast to the stub type). Add `from googleapiclient._apis.sheets.v4 import SheetsResource` under the existing `if TYPE_CHECKING:` block (stub confirmed present at googleapiclient-stubs/_apis/sheets/v4/resources.pyi: class SheetsResource with `.spreadsheets().get(spreadsheetId, ranges, includeGridData)`/`.spreadsheets().batchUpdate(spreadsheetId, body: BatchUpdateSpreadsheetRequest)`/`.spreadsheets().values().get(spreadsheetId, range)`/`.spreadsheets().values().batchUpdate(spreadsheetId, body: BatchUpdateValuesRequest)`/`.spreadsheets().values().append(spreadsheetId, range, body: ValueRange, valueInputOption, insertDataOption)`). Reuse the existing execute_google_api_request and classify_google_error as-is (no client.py behavior change beyond the new factory) — continuing the TASK-25.1.1/25.1.2 pattern. Do not add new classify_google_error mappings speculatively (HUMAN-CONFIRMED 2026-09-01: no new family unless a failure-path test in Step 4 surfaces an unmapped status).

2. app/integrations/google_workspace/sheets.py: convert get_values, get_sheet, batch_update, batch_update_values, append_values off execute_google_api_call, mirroring google_docs.py's/meet.py's exact shape:
   - Add `from typing import TYPE_CHECKING, cast` and `from integrations.google_workspace import client as google_service_client`; remove `from integrations.google_workspace.google_service import execute_google_api_call, handle_google_api_errors`.
   - Add `if TYPE_CHECKING: from googleapiclient._apis.sheets.v4 import BatchUpdateSpreadsheetRequest, BatchUpdateValuesRequest, ValueRange  # pyright: ignore[reportMissingModuleSource]`.
   - Add module-level `SHEETS_SCOPES = [\"https://www.googleapis.com/auth/spreadsheets\"]` (mirrors DOCS_SCOPES/MEET_SCOPES convention), replacing the repeated scopes= literal in each function.
   - get_values(spreadsheetId, cell_range=None, fields=None, **kwargs): pop delegated_user_email; service = get_sheets_service(scopes=SHEETS_SCOPES, delegated_user_email=...); return execute_google_api_request(service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range=cell_range, fields=fields)).
   - get_sheet(spreadsheetId, ranges, includeGridData=False, **kwargs): pop delegated_user_email; return execute_google_api_request(service.spreadsheets().get(spreadsheetId=spreadsheetId, ranges=ranges, includeGridData=includeGridData)). No message-content swallow logic here — HUMAN-CONFIRMED 2026-09-01 (option B): the 'Unable to parse range' non-critical handling relocates to incident_folder.py (Step 3), not sheets.py, because it is caller-specific business logic and decisions/outbound-clients.md forbids business logic in vendor clients. get_sheet now always raises on any HttpError, classified/logged by execute_google_api_request like every other call.
   - batch_update(spreadsheetId, body: dict, **kwargs): pop delegated_user_email; body_typed = cast(\"BatchUpdateSpreadsheetRequest\", body); return execute_google_api_request(service.spreadsheets().batchUpdate(spreadsheetId=spreadsheetId, body=body_typed)).
   - batch_update_values(spreadsheetId, cell_range, values, valueInputOption=\"USER_ENTERED\", **kwargs): pop delegated_user_email (see doubt (b): today this function silently drops **kwargs entirely, including any delegated_user_email — zero production callers pass it, so wiring it up properly here is zero-risk and brings this function in line with the other four); body_typed = cast(\"BatchUpdateValuesRequest\", {\"valueInputOption\": valueInputOption, \"data\": [{\"range\": cell_range, \"values\": values}]}); return execute_google_api_request(service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=body_typed)).
   - append_values(spreadsheetId, cell_range, body: dict, valueInputOption=\"USER_ENTERED\", insertDataOption=\"INSERT_ROWS\", **kwargs): pop delegated_user_email; body_typed = cast(\"ValueRange\", body); return execute_google_api_request(service.spreadsheets().values().append(spreadsheetId=spreadsheetId, range=cell_range, body=body_typed, valueInputOption=valueInputOption, insertDataOption=insertDataOption)).
   - Remove all five `@handle_google_api_errors` decorators. Bind results to `result: dict` before return where needed to avoid no-any-return leakage (mirrors google_docs.py/meet.py).

3. app/modules/incident/incident_folder.py — relocate the 'Unable to parse range' non-critical handling here (HUMAN-CONFIRMED 2026-09-01, option B), the only real caller that depends on it: in get_incidents_from_sheet, wrap the sheets.get_sheet(INCIDENT_LIST, \"Sheet1\", includeGridData=True) call in try/except HttpError as e: if \"Unable to parse range\" in str(e): logger.warning(...) and set incidents = None (preserves today's fall-through-to-empty-list behavior exactly); else: raise (preserves today's error-path behavior for any other HttpError). Add `from googleapiclient.errors import HttpError` import. modules/reports/google_groups.py needs NO change — its own sheets.get_sheet() call is already wrapped in a blanket `except Exception: sheet = None`, so it is unaffected by removing the swallow from sheets.py itself. modules/aws/spending.py never calls get_sheet — unaffected.

4. Prune app/bin/baselines/sdk_typing_antipatterns.txt's `integrations/google_workspace/sheets.py` entry (mirrors TASK-25.1.1/25.1.2 precedent).

5. Rework app/tests/integrations/google_workspace/test_sheets.py: the 5 tests patching `sheets.execute_google_api_call` are rebuilt to patch `sheets.google_service_client.get_sheets_service` (or `client.get_sheets_service`, matching whichever the calendar/docs test fixtures settled on) returning a MagicMock service, with the appropriate `.spreadsheets()...execute()` chain returning the same fixture dicts used today. Preserve every existing assertion on returned shape/call kwargs. Add delegated_user_email default/override coverage per function (new, since today's dispatcher-based tests never asserted delegation). Add one failure-path test per function (HttpError propagates unchanged via execute_google_api_request) — get_sheet's failure-path test must show it now raises unconditionally (no swallow), closing today's happy-path-only gap and proving the Step 3 relocation is complete.

6. Extend app/tests/unit/integrations/google_workspace/test_client.py: add `(\"get_sheets_service\", \"sheets\", \"v4\", \"https://www.googleapis.com/auth/spreadsheets\")` to the existing `test_service_factories_build_with_static_discovery_and_no_cache` / `test_service_factories_use_explicit_delegated_user_email` parametrizations.

7. Add new tests to app/tests/modules/incident/test_incident_folder.py for get_incidents_from_sheet (currently ZERO coverage of this function): (a) happy path returns parsed incident list from a mocked sheets.get_sheet dict; (b) sheets.get_sheet raises HttpError containing \"Unable to parse range\" -> function returns [] and logs a warning, does not raise; (c) sheets.get_sheet raises HttpError with a different message -> propagates uncaught; (d) sheets.get_sheet raises a non-HttpError exception -> propagates uncaught (never matched by the except clause). This is new regression coverage for the Step 3 relocation, since no existing test exercised this path.

8. Confirm the untouched Sheets consumers remain green with zero unrelated edits: modules/reports/google_groups.py and modules/aws/spending.py have no existing test files (test_spending_handler.py covers a different function, not the Sheets call site) — note in Notes that these two files have NO automated regression coverage for their Sheets call sites before or after this change; behavior-neutrality for them rests on Step 2's mechanical signature/return-shape preservation, not on a green test suite, and this gap is called out explicitly rather than silently assumed covered.

9. Re-run repo-wide checks: grep for execute_google_api_call in sheets.py (expect zero); grep for \"import sheets\"/\"sheets,\" repeat to reconfirm exactly 3 production consumers before/after; bin/check_sdk_typing.py; bin/check_deprecated_infra_client_imports.py; bin/generate_client_usage_matrix.sh.

AC-TO-STEP-TO-TEST
- AC#1 (sheets.py routes through factory + classify_google_error) -> Steps 1-2. Verified by: grep for execute_google_api_call in sheets.py returns zero; mypy resolves get_sheets_service's stub-typed return and the chained .spreadsheets()... calls with no Any leakage; Step 5 tests.
- AC#2 (3 consumer files behave identically, including get_sheet's non-critical warning preserved) -> Steps 2-3 (HUMAN-CONFIRMED: preserved via relocation to incident_folder.py, not verbatim-in-place) + Step 7 (new tests proving the relocated behavior matches today's) + Step 8 (explicit gap note for the two untested consumers).
- AC#3 (classify_google_error gains any Sheets-specific mapped families) -> Step 1's explicit decision not to speculatively extend it (HUMAN-CONFIRMED 2026-09-01), revisited only if Step 5's new failure-path tests surface an unmapped status.

TEST MATRIX
Happy path: get_values/get_sheet/batch_update/batch_update_values/append_values each return the same shape as today given a mocked successful Resource chain. Delegated-email: default-to-SRE_BOT_EMAIL and explicit-override cases for all five functions (new). Error propagation: HttpError with a classified status logs and re-raises unchanged for get_values/batch_update/batch_update_values/append_values; get_sheet now always raises (no swallow) — new test proving this. incident_folder.get_incidents_from_sheet: HttpError \"Unable to parse range\" -> [] + warning log (new); other HttpError -> propagates (new); non-HttpError -> propagates (new); happy path (new). Construction: get_sheets_service build() assertions via the existing parametrized factory tests. Regression: full existing app/tests/modules/incident/test_incident_folder.py green with Step 3's addition. Commands: cd app && uv run pytest tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/incident -v; then make test; then uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; then uv run ruff check .; then bin/check_sdk_typing.py, bin/check_deprecated_infra_client_imports.py, bin/generate_client_usage_matrix.sh.

ASSUMPTIONS AND DOUBTS (verify at impl)
(a) HUMAN-CONFIRMED DECISION (2026-09-01, question asked because this slice's plan conflicted with decisions/outbound-clients.md): the 'Unable to parse range' non-critical swallow-to-None behavior in google_service.py's handle_google_api_errors (func_name==\"get_sheet\") is business logic embedded in a vendor package, which outbound-clients.md forbids (\"Clients raise... contain no business logic\"); classify_google_error's tuple contract has no concept of swallow-and-return-None. User chose option B: relocate the swallow into incident_folder.py's get_incidents_from_sheet (its only dependent caller) rather than keeping it in sheets.py (option A, a tracked deviation) or dropping it entirely (option C, an accepted behavior change). google_groups.py needs no change since its own blanket except already absorbs this.
(b) User confirmed (via \"no new family unless a test surfaces one\") that classify_google_error should NOT gain a speculative 400/other status mapping for Sheets; only add one if Step 5's failure-path tests surface an unmapped status actually reached in practice, cited with the observed status.
(c) batch_update_values today silently drops all **kwargs (including any delegated_user_email) since the existing execute_google_api_call invocation never forwards them — confirmed zero production callers pass delegated_user_email to it (incident_folder.py, google_groups.py, spending.py all omit it). Step 2 wires delegated_user_email properly for this function per the other four's consistent pattern; zero-risk since nothing depends on the current drop.
(d) execute_google_api_request's long-term home (client.py vs. per-call-site) remains deferred to TASK-25.1.6 per the TASK-25.1.1/25.1.2 precedent; this slice continues reusing it for consistency, not as an endorsement of keeping it permanently.

BLAST RADIUS / ROLLBACK
Contained to integrations/google_workspace/{client.py,sheets.py} (edits), modules/incident/incident_folder.py (one function's error handling relocated), and their test files (test_sheets.py reworked, test_client.py extended, test_incident_folder.py gains new get_incidents_from_sheet coverage). modules/reports/google_groups.py and modules/aws/spending.py are untouched (consumers of the same public function signatures) but have no automated regression coverage for their Sheets call sites — flagged explicitly, not silently assumed safe. Single git revert restores the execute_google_api_call-based implementation and the decorator-based swallow. No ordering constraint against sibling slices (each touches disjoint files); google_service.py itself stays alive for remaining consumers (get_google_service still used elsewhere until google_directory.py/google_drive.py migrate).

SIZE GATE: fits comfortably in one PR, comparable to TASK-25.1.2. Production diff: 3 files (client.py ~15-20 new LOC for 1 factory; sheets.py ~50-70 LOC net changed, no new file; incident_folder.py ~10-12 LOC added for the relocated try/except). Test diff: test_sheets.py reworked, test_client.py extended with 1 parametrize entry, test_incident_folder.py gains ~4 new test functions. Single subsystem (Google Workspace vendor client) plus one small, tightly-scoped business-logic relocation into its sole dependent caller — no cross-cutting refactor, no packages/ changes.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:34
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. When implementing this slice, if sheets.py's migrated call sites use execute_google_api_request (or you introduce an equivalent), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's.
---

created: 2026-09-01 18:31
---
CLARIFICATION RESOLVED (2026-09-01, task-planner): the task Description's phrase 'preserve that behavior exactly' (referring to get_sheet's 'Unable to parse range' swallow) conflicted with decisions/outbound-clients.md's 'clients raise, no business logic in vendor packages' rule -- classify_google_error's tuple contract has no concept of swallow-and-return-None. Asked the human; they chose option B: relocate the swallow out of sheets.py into incident_folder.py's get_incidents_from_sheet (its only dependent caller), rather than keeping it in the vendor package (option A, a tracked deviation) or dropping it entirely (option C). Also confirmed: no speculative new classify_google_error family for Sheets -- only add one if a failure-path test surfaces an unmapped status. See the written plan for full detail.
---
<!-- COMMENTS:END -->
