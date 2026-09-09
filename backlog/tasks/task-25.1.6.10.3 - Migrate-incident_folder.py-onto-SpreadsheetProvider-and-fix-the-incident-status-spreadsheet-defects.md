---
id: TASK-25.1.6.10.3
title: >-
  Migrate incident_folder.py onto SpreadsheetProvider and fix the incident
  status spreadsheet defects
status: To Do
assignee: []
created_date: '2026-09-09 15:03'
updated_date: '2026-09-09 18:08'
labels:
  - clients
  - phase-3
  - bug
milestone: m-3
dependencies:
  - TASK-25.1.6.10.2
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/migration.md
  - decisions/testing.md
  - app/modules/incident/incident_folder.py
  - app/modules/incident/information_update.py
  - app/modules/incident/incident_status.py
  - app/modules/incident/core.py
parent_task_id: TASK-25.1.6.10
priority: high
ordinal: 161000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move modules/incident/incident_folder.py's four Sheets call sites onto infrastructure.spreadsheets.get_spreadsheet_provider(), and fix four live defects in the incident status spreadsheet path that were found while planning this migration.

CONSUMER SHAPE (decided 2026-09-09, human-directed): the legacy module calls get_spreadsheet_provider() directly. NO feature adapter and no new packages/incident subdomain - the provider already returns vendor-neutral values, so there is nothing left to translate at a feature boundary. This follows the Directory precedent (TASK-25.1.6.4/.5 had legacy modules call get_directory_provider() directly), not the Drive precedent (TASK-25.1.6.8.2/.8.3 needed adapters only because Google appProperties had to stay out of the vendor-neutral contract). incident_folder.py stays a registered, frozen legacy module; only its I/O seam changes - a bug-fix-shaped change under decisions/migration.md rule 1.

CALL SITES TO MIGRATE (grep-verified against main 2026-09-09):
- incident_folder.py:277 sheets.append_values(INCIDENT_LIST, 'Sheet1!A:A', body) -> append_values. The body wrapper ({'majorDimension','values'}) disappears; the provider takes the values matrix. The =HYPERLINK(...) formulas must still be interpreted, so the Google implementation's USER_ENTERED write mode is what preserves this.
- incident_folder.py:307 sheets.get_values(INCIDENT_LIST, cell_range='Sheet1') -> read_values, returning list[list[str]] directly instead of a dict needing .get('values', []).
- incident_folder.py:322 sheets.batch_update_values(INCIDENT_LIST, 'Sheet1!D{i+1}', [[status]]) -> update_values.
- incident_folder.py:345 sheets.get_sheet(INCIDENT_LIST, 'Sheet1', includeGridData=True) -> read_cells, returning list[list[SheetCell]]. The row walk collapses: the sheets[0].data[0].rowData indexing moves into the provider, and values[n].get('formattedValue')/.get('hyperlink') become cell.formatted_value/cell.link.

PARSE-RANGE RULE STAYS CALLER-SIDE (TASK-25.1.6's standing instruction). Today get_incidents_from_sheet catches HttpError, swallows 'Unable to parse range' with a warning and returns [], and re-raises anything else. After migration TASK-25.1.6.10.2's provider returns OperationStatus.NOT_FOUND for the parse-range case, so the swallow becomes an is-NOT_FOUND check - same behavior, no string matching at the caller.

CRITICAL: PRESERVE 'EMPTY' VS 'FAILED'. Do not let a non-parse-range failure return []. modules/incident/core.py:241 _add_incident_to_sheet calls get_incidents_from_sheet inside a try/except and concludes 'not already in sheet' from an empty list; if an API failure silently became [], that path would WRITE A DUPLICATE ROW. Today the HttpError propagates and core.py's except catches it. Preserve that control flow by raising a module-level IncidentSheetError (mirroring the DirectoryReportError precedent) on any classified failure that is not the parse-range NOT_FOUND case. core.py's except Exception still catches it; modules/dev/incident.py:41 is the other caller and surfaces it.

FOUR DEFECTS FIXED HERE (all human-approved 2026-09-09; folded into this slice rather than a separate bug task):
(A) ROOT CAUSE OF THE REPORTED PRODUCTION BUG. add_new_incident_to_list writes column E as =HYPERLINK(url, '#{slug}') where slug has no 'incident-' prefix, so the sheet's channel cell displays '#2026-09-09-foo'. incident_status.py:57 normalizes correctly via return_channel_name(); information_update.py:313 does NOT - it passes the raw DB channel_name ('incident-2026-09-09-foo'), so 'if channel_name in row' never matches, update_spreadsheet_incident_status returns False, and the row stays 'In Progress' forever. This is why changing status through the /sre incident show modal updates the DB and the document but not the spreadsheet. Fix: information_update.py:313 passes incident_folder.return_channel_name(channel_name), matching incident_status.py:57.
(B) update_spreadsheet_incident_status returns False silently when no row matches - it logs nothing, and neither caller inspects the return value, so the failure is invisible in production. Fix: log a warning with the searched channel name and status on the no-match path.
(C) information_update.py posts '<@user> has updated the field status to X' regardless of whether the spreadsheet write succeeded. Fix: surface a failed spreadsheet update to the user, consistent with incident_status.py's existing respond() warning on the same failure.
(D) core.py:242 _add_incident_to_sheet derives slug as channel_name.replace('incident-', ''), yielding 'dev-2026-09-09-foo' for dev channels, while incident_conversation.py:39 creates the slug with no dev- component. The recreate-missing-resources path therefore compares and would write an inconsistent slug. Fix: derive the slug the same way the creation path does.

NOT IN SCOPE: modules/aws/spending.py and the deletion of integrations/google_workspace/sheets.py (TASK-25.1.6.10.4), modules/reports (TASK-25.1.6.10.1), google_drive.py (TASK-25.1.6.10.5), LEGACY_FOLDER_DISPLAY_LIMIT (TASK-81), any Slack view/i18n change beyond defect C's failure message, and relocating app/tests/modules/incident/ out of the legacy test tree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 incident_folder.py's four Sheets call sites use infrastructure.spreadsheets.get_spreadsheet_provider(); the module no longer imports integrations.google_workspace.sheets or googleapiclient, and no feature adapter or new packages/incident subdomain is created
- [ ] #2 get_incidents_from_sheet returns [] with a warning only for the provider's parse-range NOT_FOUND result, and raises IncidentSheetError for any other classified failure, so core.py::_add_incident_to_sheet cannot mistake an API failure for an empty sheet and write a duplicate row; both paths are covered by tests
- [ ] #3 The parsed incident dicts from get_incidents_from_sheet are byte-for-byte identical to today's for the same sheet contents (channel_id regex extraction, TBC fallbacks, header-row skip, short-row skip, days lookback filter), proven against the existing fixture in app/tests/modules/incident/test_incident_folder.py
- [ ] #4 information_update.py passes return_channel_name(channel_name) to update_spreadsheet_incident_status, matching incident_status.py; a test proves the value reaching the provider matches the '#slug' form actually written to the sheet by add_new_incident_to_list
- [ ] #5 update_spreadsheet_incident_status logs a warning when no row matches instead of returning False silently, and information_update.py surfaces a failed spreadsheet update to the user instead of unconditionally confirming the field change
- [ ] #6 core.py::_add_incident_to_sheet derives the incident slug the same way incident_conversation.py does, so dev incident channels produce a consistent slug on the recreate path
- [ ] #7 Existing Sheets coverage in app/tests/modules/incident/test_incident_folder.py is preserved at the new provider seam (Protocol-shaped fakes returning real OperationResult values, per decisions/testing.md), with no MagicMock standing in for the subject under test
- [ ] #8 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass
- [ ] #9 update_spreadsheet_incident_status raises IncidentSheetError for any classified read_values/update_values failure that is not the 'empty sheet' or 'no matching row' business outcome; those two outcomes still return False with a warning log (human-approved 2026-09-09 planning decision)
- [ ] #10 add_new_incident_to_list raises IncidentSheetError when append_values returns a classified failure, instead of silently returning a falsy value (human-approved 2026-09-09 planning decision)
- [ ] #11 information_update.py posts an additional client.chat_postMessage warning when update_spreadsheet_incident_status returns False, without removing the existing '<@user> has updated the field status to X' confirmation message (human-approved 2026-09-09 planning decision)
- [ ] #12 core.py::_create_document_bookmark also derives its slug via the corrected channel_slug helper (same fix as defect D's _add_incident_to_sheet), so dev-channel document lookup/creation and the incident-list slug stay consistent (scope widened by human decision 2026-09-09)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read/grep/empirically verified against main, 2026-09-09)

Call sites migrated (grep-verified, unchanged from the task description):
incident_folder.py:277 sheets.append_values(INCIDENT_LIST,'Sheet1!A:A',body) -> append_values
incident_folder.py:307 sheets.get_values(INCIDENT_LIST,cell_range='Sheet1') -> read_values
incident_folder.py:322 sheets.batch_update_values(INCIDENT_LIST,'Sheet1!D{i+1}',[[status]]) -> update_values
incident_folder.py:345 sheets.get_sheet(INCIDENT_LIST,'Sheet1',includeGridData=True) -> read_cells
No other sheets.* call sites exist in incident_folder.py (grep confirmed exactly these 4).

SpreadsheetProvider (shipped by TASK-25.1.6.10.2, app/infrastructure/spreadsheets/): read_values(spreadsheet_id,a1_range)->OperationResult[list[list[str]]], update_values(...)->OperationResult[None], append_values(...)->OperationResult[None], read_cells(...)->OperationResult[list[list[SheetCell]]]. SheetCell(formatted_value,link,provider). RANGE_NOT_FOUND is exported from infrastructure.spreadsheets (package boundary, not a vendor detail) and is the error_code set only when the Google implementation classifies an HttpError 400 'Unable to parse range' - re-verified in app/infrastructure/spreadsheets/google.py::_map_sdk_exception. get_spreadsheet_provider() is a cached singleton factory, resolved via a direct call inside function bodies - the Directory precedent (app/modules/reports/google_groups.py::generate_group_members_report calling get_directory_provider() inline, and its test app/tests/unit/modules/reports/test_google_groups_report.py patching module.get_directory_provider with patch.object(module,'get_directory_provider', lambda: fake)) is the established pattern for legacy modules + Path A providers and is reused here verbatim. TASK-25.1.6.13 (Done) configures retry once at construction; nothing in this task touches retry.

CURRENT BEHAVIOR PRECISELY RE-VERIFIED PER FUNCTION (not assumed):
- get_incidents_from_sheet: today wraps sheets.get_sheet in try/except HttpError, swallows only 'Unable to parse range' (returns [] with a warning), re-raises everything else (HttpError and any other exception type) uncaught. AC#2/#3 target this exactly.
- update_spreadsheet_incident_status: today has NO try/except around sheets.get_values or sheets.batch_update_values - ANY failure (including a hypothetical parse-range HttpError) already propagates uncaught to the caller. Only two 'expected' non-exception outcomes return False: invalid status (checked before any I/O) and an empty 'values' list post-fetch. The 'iterate rows, no match found' branch falls off the end of the for-loop and returns False with NO log line today (defect B). This is the exact reason update_spreadsheet_incident_status must raise IncidentSheetError on ANY provider failure (including a hypothetical RANGE_NOT_FOUND) rather than special-casing NOT_FOUND like get_incidents_from_sheet does - unlike get_incidents_from_sheet, this function never had a swallow branch, so introducing one now would be a new, unrequested behavior change. Confirmed with the human during planning (see Decisions below).
- add_new_incident_to_list: today calls sheets.append_values with no try/except; both callers (core.py:252 inside _add_incident_to_sheet's try/except Exception, core.py:483 inside handle_new_incident_conversation's broader flow) never check its return value - they rely on propagation-or-silence. Confirmed with the human: this function must also raise IncidentSheetError on failure so core.py's error accumulation is not fooled into logging 'success'.
- information_update.py:313 passes the RAW channel_name (e.g. 'incident-2026-09-09-foo') to update_spreadsheet_incident_status, not through return_channel_name like incident_status.py:57 does - defect A, confirmed by direct read of both files.
- core.py has THREE places deriving a channel-name-based slug: line ~166 _create_document_bookmark ('slug = channel_name.replace(\"incident-\",\"\")' - buggy, same defect-D pattern), line ~242 _add_incident_to_sheet (same buggy pattern, the one named in the task), and recreate_missing_resources's incident_name fallback ('channel_name.replace(\"incident-\",\"\").replace(\"dev-\",\"\")' - already correct, proving the two-step strip is the right idea, just missing from the two buggy call sites). Human decided (2026-09-09 planning) to fix _create_document_bookmark too since it carries the identical bug and one shared helper fixes both cleanly.
- test_incident_folder.py, test_information_update.py, test_recreate_missing_resources.py, test_incident_status.py all read and diffed line-by-line against this plan (see Step 6-8). incident_status.py needs ZERO code changes: it already calls return_channel_name correctly and its tests already fully mock incident_folder, so nothing there depends on this migration's internals.

DECISIONS CONFIRMED WITH THE HUMAN DURING THIS PLANNING SESSION (2026-09-09, folded into AC#9-12):
1. update_spreadsheet_incident_status raises IncidentSheetError on any classified read_values/update_values failure; only 'empty sheet' and 'no matching row' remain False-with-warning outcomes.
2. add_new_incident_to_list raises IncidentSheetError on any classified append_values failure.
3. information_update.py posts an ADDITIONAL client.chat_postMessage warning on a False return, keeping the existing confirmation message (not replacing it).
4. core.py::_create_document_bookmark's slug bug is fixed in this task too, sharing the same helper as _add_incident_to_sheet.

STEP 1 - app/modules/incident/incident_folder.py imports and module-level additions
Remove: 'from googleapiclient.errors import HttpError', 'from integrations.google_workspace import sheets'.
Add: 'from infrastructure.operations import OperationStatus' and 'from infrastructure.spreadsheets import RANGE_NOT_FOUND, get_spreadsheet_provider'.
Add a module-level exception, mirroring modules/reports/google_groups.py::DirectoryReportError's shape (that file is deleted by TASK-25.1.6.10.1, so no import - just the same pattern copied once):
  class IncidentSheetError(Exception):
      def __init__(self, message: str, error_code: str | None = None) -> None:
          super().__init__(message); self.message = message; self.error_code = error_code

STEP 2 - incident_folder.py::channel_slug (new) and return_channel_name (refactored, behavior-preserving)
Add:
  def channel_slug(channel_name: str) -> str:
      dev_prefix = \"incident-dev-\"; prefix = \"incident-\"
      if channel_name.startswith(dev_prefix):
          return channel_name.removeprefix(dev_prefix)
      return channel_name.removeprefix(prefix)
Refactor return_channel_name to delegate to it without changing its output:
  def return_channel_name(input_str: str) -> str:
      if not input_str.startswith(\"incident-\"):
          return input_str
      return \"#\" + channel_slug(input_str)
Manually traced against all 6 existing test_return_channel_name_* cases (with/without prefix, dev prefix, empty string, prefix-only, dev-prefix-only) - all produce identical output to today's implementation. These tests are NOT changed; they are the regression guard for this refactor.

STEP 3 - incident_folder.py::add_new_incident_to_list
Replace the body-wrapper + sheets.append_values call with:
  result = get_spreadsheet_provider().append_values(INCIDENT_LIST, \"Sheet1!A:A\", incident_data)
  if not result.is_success:
      logger.error(\"add_new_incident_to_list_failed\", error=result.message, error_code=result.error_code)
      raise IncidentSheetError(result.message, result.error_code)
  return True
incident_data stays the same list-of-lists literal already built (majorDimension/values wrapper dict is deleted - the provider's append_values takes the plain matrix). Docstring updated: 'Returns True on success. Raises IncidentSheetError if the write fails.'

STEP 4 - incident_folder.py::update_spreadsheet_incident_status
  def update_spreadsheet_incident_status(channel_name, status=\"Closed\"):
      if status not in valid_statuses:  # unchanged
          logger.warning(...); return False
      sheet_name = \"Sheet1\"
      provider = get_spreadsheet_provider()
      result = provider.read_values(INCIDENT_LIST, sheet_name)
      if not result.is_success:
          logger.error(\"update_incident_spreadsheet_error\", channel=channel_name, status=status, error=result.message, error_code=result.error_code)
          raise IncidentSheetError(result.message, result.error_code)
      values = result.data or []
      if len(values) == 0:
          logger.warning(\"update_incident_spreadsheet_error\", channel=channel_name, status=status, error=\"No values found in the sheet\")
          return False
      for i, row in enumerate(values):
          if channel_name in row:
              update_result = provider.update_values(INCIDENT_LIST, f\"{sheet_name}!D{i + 1}\", [[status]])
              if not update_result.is_success:
                  logger.error(\"update_incident_spreadsheet_error\", channel=channel_name, status=status, error=update_result.message, error_code=update_result.error_code)
                  raise IncidentSheetError(update_result.message, update_result.error_code)
              return True
      logger.warning(\"update_incident_spreadsheet_error\", channel=channel_name, status=status, error=\"Channel not found in the sheet\")  # defect B
      return False
Note: no NOT_FOUND/RANGE_NOT_FOUND special-case here (see grounding above) - ANY read_values/update_values failure raises, preserving today's 'no try/except, anything propagates' behavior.

STEP 5 - incident_folder.py::get_incidents_from_sheet
  def get_incidents_from_sheet(days=0) -> list:
      date_lookback_str = ...  # unchanged
      result = get_spreadsheet_provider().read_cells(INCIDENT_LIST, \"Sheet1\")
      if not result.is_success:
          if result.status is OperationStatus.NOT_FOUND and result.error_code == RANGE_NOT_FOUND:
              logger.warning(\"get_incidents_from_sheet_unable_to_parse_range\", error=result.message)
              return []
          logger.error(\"get_incidents_from_sheet_failed\", error=result.message, error_code=result.error_code)
          raise IncidentSheetError(result.message, result.error_code)
      row_data = result.data or []
      incidents_details = []
      for row in row_data[1:]:
          if not row or len(row) < 5:
              continue
          channel_cell = row[4]
          channel_url = channel_cell.link
          channel_id = None
          if channel_url:
              match = re.search(r\"https://gcdigital\\.slack\\.com/archives/(\\w+)\", channel_url)
              if match:
                  channel_id = match.group(1)
          channel_name = channel_cell.formatted_value
          channel_name = \"TBC\" if not channel_name else channel_name[1:]
          incident_details = {
              \"channel_id\": channel_id, \"channel_name\": channel_name,
              \"name\": row[1].formatted_value, \"user_id\": \"\", \"teams\": [row[2].formatted_value],
              \"report_url\": row[1].link, \"status\": row[3].formatted_value,
              \"created_at\": row[0].formatted_value, \"meet_url\": \"TBC\",
          }
          if incident_details[\"channel_id\"] is None:
              continue
          if days > 0 and incident_details[\"created_at\"] < date_lookback_str:
              continue
          incidents_details.append(incident_details)
      return incidents_details
Index-for-index identical to today's values[n].get('formattedValue')/.get('hyperlink') walk, just against SheetCell attributes instead of dict keys - this is what makes AC#3's byte-for-byte requirement achievable.

STEP 6 - app/modules/incident/information_update.py (defects A and C)
Replace:
  incident_folder.update_spreadsheet_incident_status(channel_name, value)
with:
  spreadsheet_updated = incident_folder.update_spreadsheet_incident_status(
      incident_folder.return_channel_name(channel_name), value
  )
  if not spreadsheet_updated:
      client.chat_postMessage(
          channel=channel_id,
          text=f\"Could not update the incident status in the spreadsheet for channel {channel_name}.\",
      )
The existing unconditional 'has updated the field status to X' message below is UNCHANGED (per the human's confirmed 'additional message' design) - both messages can be posted when the write fails. A genuine IncidentSheetError raised by update_spreadsheet_incident_status still propagates uncaught here exactly as an HttpError would have today (no new try/except added) - this preserves, not changes, today's crash-on-real-failure behavior.

STEP 7 - app/modules/incident/core.py (defect D, widened to _create_document_bookmark)
Line ~166 (_create_document_bookmark): 'slug = channel_name.replace(\"incident-\", \"\")' -> 'slug = incident_folder.channel_slug(channel_name)'.
Line ~242 (_add_incident_to_sheet): 'slug = channel_name.replace(\"incident-\", \"\")' -> 'slug = incident_folder.channel_slug(channel_name)'.
No other line in core.py changes. The pre-existing, already-correct 'channel_name.replace(\"incident-\",\"\").replace(\"dev-\",\"\")' fallback inside recreate_missing_resources (deriving incident_name, not the sheet/document slug) is NOT touched - it is a different variable for a different purpose and is already correct.

STEP 8 - tests: app/tests/modules/incident/test_incident_folder.py
Add a FakeSpreadsheetProvider (Protocol-shaped, mirrors FakeDirectory in test_google_groups_report.py) exposing read_values_result/update_values_result/append_values_result/read_cells_result (each defaulting to OperationResult.success(...)) and *_calls lists recording args; patched in via patch.object(incident_folder, \"get_spreadsheet_provider\", lambda: fake).
Replace the sheets-mock-based tests:
  test_add_new_incident_to_list -> test_add_new_incident_to_list_success (assert append_values called with (INCIDENT_LIST, \"Sheet1!A:A\", <matrix, no wrapper dict>); assert returns True) and test_add_new_incident_to_list_raises_on_failure (append_values_result = OperationResult.error(...); pytest.raises(IncidentSheetError)).
  test_update_spreadsheet_incident_status_invalid_status -> unchanged assertions, no provider interaction.
  test_update_spreadsheet_incident_status_empty_values -> read_values_result = OperationResult.success(data=[]); same warning assertion as today.
  NEW test_update_spreadsheet_incident_status_read_failure_raises -> read_values_result = OperationResult.error(status=TRANSIENT_ERROR,...); pytest.raises(IncidentSheetError).
  test_update_spreadsheet_incident_status_channel_found -> read_values_result returns the matching row; assert update_values called with (INCIDENT_LIST, \"Sheet1!D1\", [[\"Closed\"]]); assert True.
  NEW test_update_spreadsheet_incident_status_update_failure_raises -> matching row found, update_values_result = OperationResult.error(...); pytest.raises(IncidentSheetError).
  test_update_spreadsheet_incident_status_channel_not_found -> add the NEW logger.warning assertion for defect B ('Channel not found in the sheet').
  test_return_channel_name_* -> unchanged (regression guard for Step 2's refactor).
  NEW test_channel_slug_* (6 cases mirroring test_return_channel_name_* exactly, pinning the new helper directly).
  test_get_incidents_from_sheet_returns_parsed_incidents -> _incident_row_data() fixture rewritten to build list[list[SheetCell]] (2 rows: header + one data row) instead of the raw Google dict; same expected incidents dict asserted (AC#3).
  test_get_incidents_from_sheet_swallows_unable_to_parse_range -> renamed test_get_incidents_from_sheet_swallows_range_not_found; read_cells_result = OperationResult.error(status=OperationStatus.NOT_FOUND, error_code=RANGE_NOT_FOUND, message=\"Unable to parse range: Sheet1\"); assert [] and logger.warning called.
  test_get_incidents_from_sheet_propagates_other_http_error -> renamed test_get_incidents_from_sheet_raises_on_other_failure; read_cells_result = OperationResult.error(status=OperationStatus.TRANSIENT_ERROR, error_code=\"X\", message=\"Internal error\"); pytest.raises(IncidentSheetError).
  test_get_incidents_from_sheet_propagates_non_http_error -> REMOVED (obsolete: the provider boundary never lets an arbitrary Python exception escape - HttpError classification is TASK-25.1.6.10.2's concern, already tested there; nothing in incident_folder.py can raise a bare ValueError from this call anymore). Explicitly named here so its removal isn't mistaken for accidental coverage loss.

STEP 9 - tests: app/tests/modules/incident/test_information_update.py
test_handle_update_field_submission_dropdown_type (status branch): set mock_incident_folder.update_spreadsheet_incident_status.return_value = True and mock_incident_folder.return_channel_name.return_value = incident_data[\"channel_name\"] (identity passthrough for a non-prefixed test fixture name); add assertion mock_incident_folder.return_channel_name.assert_called_once_with(incident_data[\"channel_name\"]); update the update_spreadsheet_incident_status assertion to assert_called_once_with(mock_incident_folder.return_channel_name.return_value, \"Closed\"); assert mock_client.chat_postMessage.call_count == 1 (only the confirmation, no warning).
NEW test_handle_update_field_submission_status_type_spreadsheet_update_failed: same setup but mock_incident_folder.update_spreadsheet_incident_status.return_value = False; assert mock_client.chat_postMessage.call_count == 2 and assert_any_call for both the warning text and the unchanged confirmation text.
test_handle_update_field_submission_date_type / _text_type / _not_supported: unchanged (they already assert update_spreadsheet_incident_status.assert_not_called(), unaffected by this change).

STEP 10 - tests: app/tests/modules/incident/test_recreate_missing_resources.py
NEW test_add_incident_to_sheet_dev_channel_uses_consistent_slug: patch modules.incident.core.incident_folder, but bind mock_incident_folder.channel_slug = incident_folder.channel_slug (the REAL function, not a further mock) so the test exercises real prefix-stripping logic while I/O methods stay stubbed; call core._add_incident_to_sheet(...) directly (mirroring the file's existing direct-call precedent for core._create_database_record) with channel_name=\"incident-dev-2024-01-01-foo\"; assert add_new_incident_to_list is called with slug \"2024-01-01-foo\" (not \"dev-2024-01-01-foo\").
NEW test_create_document_bookmark_dev_channel_uses_consistent_slug: same real-channel_slug-binding technique; call core._create_document_bookmark(...) directly with the same dev channel name; assert incident_document.create_incident_document is called with slug \"2024-01-01-foo\".
Existing tests in this file (test_recreate_missing_resources_all_missing/_all_exist/_partial_missing/_channel_info_error/_unknown_product/_meet_creation_fails, test_contract_create_database_record_uses_environment_not_prefix) re-verified: none use a dev-prefixed channel_name and none assert a specific slug argument to create_incident_document or add_new_incident_to_list (only assert_called_once()/assert_not_called()) - so none change.

STEP 11 - test_incident_status.py: NO CHANGES. Re-verified: it already fully mocks incident_folder and already calls return_channel_name correctly; nothing in it depends on incident_folder's internals.

STEP 12 - guardrails
cd app && uv run pytest tests/modules/incident/test_incident_folder.py tests/modules/incident/test_information_update.py tests/modules/incident/test_recreate_missing_resources.py tests/modules/incident/test_incident_status.py tests/modules/incident/test_core.py -q (if the last one exists; otherwise the recreate/incident_helper files cover core.py)
cd app && uv run mypy modules/incident/incident_folder.py modules/incident/information_update.py modules/incident/core.py
cd app && uv run ruff check .
cd app && uv run python bin/check_sdk_typing.py
grep -rn 'integrations.google_workspace.sheets\|googleapiclient' app/modules/incident/incident_folder.py  -> expect no matches (AC#1).

AC TRACEABILITY
AC#1 (four call sites onto get_spreadsheet_provider(), no sheets/googleapiclient import, no adapter/subdomain) -> Steps 1,3,4,5; proven by the Step 12 grep and the rewritten Step 8 tests.
AC#2 (get_incidents_from_sheet: NOT_FOUND->[]+warning, else IncidentSheetError) -> Step 5; proven by the two renamed/added tests in Step 8.
AC#3 (byte-for-byte parsed incidents) -> Step 5; proven by test_get_incidents_from_sheet_returns_parsed_incidents against the rebuilt SheetCell fixture.
AC#4 (information_update passes return_channel_name(channel_name)) -> Step 6; proven by Step 9's updated assertion.
AC#5 (warning log on no-match; user-facing failure surfaced) -> Steps 4,6; proven by Step 8's channel_not_found warning assertion and Step 9's new failure test.
AC#6 (core.py slug fix matches incident_conversation.py's convention) -> Step 7; proven by Step 10's two new tests.
AC#7 (Protocol-shaped fakes, no MagicMock on the subject) -> Step 8's FakeSpreadsheetProvider.
AC#8 (gates) -> Step 12.
AC#9 (update_spreadsheet_incident_status raises on genuine failure) -> Step 4; proven by the new read/update failure tests in Step 8.
AC#10 (add_new_incident_to_list raises on failure) -> Step 3; proven by Step 8's new raises test.
AC#11 (information_update posts additional warning, keeps confirmation) -> Step 6; proven by Step 9's new failure test asserting call_count == 2.
AC#12 (_create_document_bookmark shares the slug fix) -> Step 7; proven by Step 10's second new test.

TEST MATRIX
Happy path: all four provider methods succeed through their respective incident_folder functions; return_channel_name/channel_slug unchanged for all 6 existing cases.
Boundary: empty values list, no-matching-row, header-only sheet, row shorter than 5 cells, missing hyperlink/formattedValue, dev-prefixed channel name for both core.py slug sites.
Failure: RANGE_NOT_FOUND swallowed only in get_incidents_from_sheet; every other classified failure (TRANSIENT_ERROR/PERMANENT_ERROR/UNAUTHORIZED/NOT_FOUND-not-RANGE_NOT_FOUND) raises IncidentSheetError from all three migrated write/read functions; a raised IncidentSheetError still reaches core.py's except Exception (caught, logged into results['errors']) and still propagates uncaught through information_update.py and dev/incident.py's load_incidents (both unchanged, no new try/except added there).
Not covered (intentional, per NOT IN SCOPE): modules/aws/spending.py, integrations/google_workspace/sheets.py deletion, any change to LEGACY_FOLDER_DISPLAY_LIMIT, relocating app/tests/modules/incident/.

ASSUMPTIONS AND DOUBTS FOR HUMAN REVIEW
(a) The exact wording of information_update.py's new warning message ('Could not update the incident status in the spreadsheet for channel {channel_name}.') is my proposal, not specified by any AC or decision record - adjust in review if different wording/i18n handling is wanted.
(b) channel_slug() is exposed as a public (non-underscore) function on incident_folder.py so core.py can call it across module boundaries - consistent with return_channel_name's existing public-helper precedent in the same file.
(c) recreate_missing_resources's incident_name fallback ('channel_name.replace(\"incident-\",\"\").replace(\"dev-\",\"\")') is deliberately left untouched - it derives a different value (display name) for a different purpose and is already correct; do not 'fix' it by routing it through channel_slug() in this task.

BLAST RADIUS AND ROLLBACK
Production changes: 3 files (incident_folder.py, information_update.py, core.py), all inside the already-frozen-but-bugfixable modules/incident package (decisions/migration.md rule 1's bug-fix carve-out; no new capability, no new packages/incident subdomain). No settings, lifespan, terraform, or CI changes. Estimated production diff: ~120-150 changed lines in incident_folder.py (four function bodies plus the new exception and helper), ~10-15 lines in information_update.py, ~4-6 lines in core.py - roughly 150-170 production LOC across 3 files, one subsystem (incident feature legacy modules consuming the new Path A provider). A single git revert restores today's sheets.py-based behavior exactly, since integrations.google_workspace.sheets is untouched and still exists (AC#1's boundary, and TASK-25.1.6.10.1/.10.4 have not run yet).

SIZE GATE
This PR mixes a mechanical migration (swap sheets.* client calls for the provider) with four behavior fixes (A-D) at the SAME call sites - technically triggers the implementation-planning skill's rule #3 (mechanical + behavior in one PR). This mixing is NOT a new decision made in this plan: it is the task's own pre-approved framing (\"FOUR DEFECTS FIXED HERE...folded into this slice rather than a separate bug task\", explicitly human-approved 2026-09-09 at task-creation time, checkpoint #1). Recommending against further decomposition because: (1) the migration and each defect fix land in the SAME function body (e.g. update_spreadsheet_incident_status's provider swap and its defect-B warning are one inseparable edit), so a mechanical-only PR would ship half-finished, semantically-incomplete functions; (2) total size is modest - 3 production files, ~150-170 LOC, one subsystem, no mixed refactor+behavior ACROSS unrelated areas (it's the same 4 call sites throughout); (3) well under the 400 LOC/10-file thresholds. If the human disagrees with carrying this mixing forward, the natural split would be Slice 1 (mechanical: migrate all 4 call sites onto the provider with IDENTICAL behavior, i.e. still silently return False/[] on any failure) then Slice 2 (behavior: defects A-D plus the IncidentSheetError raise-on-failure change) - flagging this as an option, not proceeding with it unless requested.
<!-- SECTION:PLAN:END -->
