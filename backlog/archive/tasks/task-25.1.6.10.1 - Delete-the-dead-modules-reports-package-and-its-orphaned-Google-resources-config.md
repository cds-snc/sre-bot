---
id: TASK-25.1.6.10.1
title: >-
  Delete the dead modules/reports package and its orphaned Google resources
  config
status: Done
assignee:
  - '@me'
created_date: '2026-09-09 15:02'
updated_date: '2026-09-09 20:48'
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
- [x] #1 app/modules/reports/ is deleted in full (__init__.py, core.py, google_groups.py); no module, test, or registration references modules.reports anywhere in the repo
- [x] #2 app/tests/unit/modules/reports/ is deleted; no report behavior, help text, or A1 helper is migrated or recreated elsewhere
- [x] #3 grep -rn 'time.sleep' over app/modules/reports returns nothing because the package is gone; the 1.1s per-group pacer is removed with it and not reintroduced
- [x] #4 GoogleResourcesSettings.google_groups_reports_folder_id and the 'rep' entry in its docstring example are removed, along with any test asserting them; no terraform or SSM change is made
- [x] #5 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deleted app/modules/reports/__init__.py, core.py, google_groups.py and app/tests/unit/modules/reports/. Removed the orphaned GoogleResourcesSettings reports entry and google_groups_reports_folder_id property. Verification: no reports source/test files, modules.reports references, report setting references, or reports time.sleep remain in app; google_drive.py remains present; Ruff and bin/check_sdk_typing.py pass; human reports make test green. AC #5 is intentionally unchecked because integrations/google_workspace/sheets.py was deleted by TASK-25.1.6.10.4 in the same approved cleanup session, so this task's historical NOT IN SCOPE retention condition is no longer true. AC #6 remains unchecked because repository-wide mypy reports 65 pre-existing errors in unrelated files; resolve that existing typing debt before checking it.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-09 20:43
---
Human confirmed make test completed successfully on 2026-09-09. This supports the full-suite portion of AC#6; AC#6 remains unchecked because make lint runs Ruff only and the repository-wide mypy command previously reported 65 unrelated errors.
---

created: 2026-09-09 20:46
---
Human-approved scope correction: removed the obsolete AC requiring integrations/google_workspace/sheets.py and google_drive.py to remain. Sheets was intentionally deleted by TASK-25.1.6.10.4; Google Drive deletion is owned by TASK-25.1.6.10.5. Human also approved checking the quality-gate AC while treating the existing whole-tree mypy errors as pre-existing debt; make test, Ruff, and SDK typing evidence are green.
---
<!-- COMMENTS:END -->
