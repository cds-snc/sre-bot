---
id: TASK-25.1.6.10.3
title: >-
  Migrate incident_folder.py onto SpreadsheetProvider and fix the incident
  status spreadsheet defects
status: To Do
assignee: []
created_date: '2026-09-09 15:03'
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
<!-- AC:END -->
