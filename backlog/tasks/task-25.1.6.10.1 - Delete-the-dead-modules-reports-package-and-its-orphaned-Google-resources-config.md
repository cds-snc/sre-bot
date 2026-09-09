---
id: TASK-25.1.6.10.1
title: >-
  Delete the dead modules/reports package and its orphaned Google resources
  config
status: To Do
assignee: []
created_date: '2026-09-09 15:02'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/migration.md
  - decisions/outbound-clients.md
  - app/modules/reports/core.py
  - app/modules/reports/google_groups.py
  - app/infrastructure/configuration/integrations/google.py
parent_task_id: TASK-25.1.6.10
priority: high
ordinal: 159000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Delete the whole app/modules/reports/ package. It is unreachable dead code: modules/reports/core.py::reports_command has ZERO callers repo-wide (grep-verified 2026-09-09) - it is not in server/lifespan.py::_register_legacy_handlers(), and no /sre subcommand dispatcher references it. The '/sre reports google-groups' and '/sre reports google-groups-members' help text describes commands that cannot be invoked.

WHY DELETION AND NOT MIGRATION (decided 2026-09-08, reaffirmed 2026-09-09 with human review): the feature is unused, so migrating it onto DirectoryProvider/SpreadsheetProvider would be work spent carrying dead behavior across an architectural seam. A future reporting capability is a new feature task, not this one. Do not recreate any report behavior here.

WHAT GOES WITH IT (all deletions, no replacement):
- app/modules/reports/__init__.py, core.py, google_groups.py
- app/tests/unit/modules/reports/ (test_google_groups_report.py, the TASK-25.1.6.1 characterization suite, plus its __init__.py if present)
- The two _a1_range / _sheet_title A1-quoting helpers shipped by TASK-25.1.6.12 (that bug fix lived only in this module; it is superseded by deletion, not regressed)
- The time.sleep(1.1) per-group pacing loop at google_groups.py:127 - the last time.sleep rate limiter in this migration series
- DirectoryReportError
- 3 Sheets call sites (sheets.get_sheet, sheets.batch_update, sheets.batch_update_values) and 2 legacy Drive call sites (google_drive.find_files_by_name, google_drive.create_file)

CONFIG CLEANUP (folded in, human-directed 2026-09-09): app/infrastructure/configuration/integrations/google.py::GoogleResourcesSettings.google_groups_reports_folder_id becomes orphaned - delete the property and the 'rep' block from the class docstring's GOOGLE_RESOURCES example. No terraform/SSM change is required: GOOGLE_RESOURCES is a single JSON env var and _get_resource tolerates unknown keys, so a deployed payload still carrying 'rep' remains valid. Check app/tests/unit/infrastructure/configuration/ for any assertion on that property and remove it.

NOT IN SCOPE: integrations/google_workspace/sheets.py (deleted by TASK-25.1.6.10.4), integrations/google_workspace/google_drive.py (deleted by TASK-25.1.6.10.5), and any change to modules/incident or modules/aws.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/reports/ is deleted in full (__init__.py, core.py, google_groups.py); no module, test, or registration references modules.reports anywhere in the repo
- [ ] #2 app/tests/unit/modules/reports/ is deleted; no report behavior, help text, or A1 helper is migrated or recreated elsewhere
- [ ] #3 grep -rn 'time.sleep' over app/modules/reports returns nothing because the package is gone; the 1.1s per-group pacer is removed with it and not reintroduced
- [ ] #4 GoogleResourcesSettings.google_groups_reports_folder_id and the 'rep' entry in its docstring example are removed, along with any test asserting them; no terraform or SSM change is made
- [ ] #5 integrations/google_workspace/sheets.py and integrations/google_workspace/google_drive.py are NOT deleted by this task and still exist for their remaining consumers
- [ ] #6 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->
