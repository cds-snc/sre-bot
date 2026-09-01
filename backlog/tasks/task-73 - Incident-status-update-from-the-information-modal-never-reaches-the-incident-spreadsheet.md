---
id: TASK-73
title: >-
  Incident status update from the information modal never reaches the incident
  spreadsheet
status: To Do
assignee: []
created_date: '2026-09-01 19:28'
updated_date: '2026-09-01 19:28'
labels:
  - bug
  - incident
  - sheets
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/modules/incident/incident_folder.py
  - app/modules/incident/information_update.py
  - app/modules/incident/incident_status.py
priority: medium
ordinal: 129000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Changing an incident's status from the incident-information modal never updates the incident Google Sheet. The DynamoDB record and the incident document are updated, no exception is raised, and nothing is logged - so the failure is completely silent and looks like a Sheets API problem.

ROOT CAUSE (investigated 2026-09-01 while validating TASK-25.1.3; NOT caused by that migration)

The incident list spreadsheet stores the channel column in slug form. Confirmed against the live sheet:

    ['2026-09-01', 'testing new sheets api', 'Site reliability engineering', 'In Progress', '#2026-09-01-testing-new-sheets-api']

incident_folder.update_spreadsheet_incident_status matches rows with `if channel_name in row` - exact element membership against that slug form.

- modules/incident/incident_status.py:57 normalizes first: update_spreadsheet_incident_status(incident_folder.return_channel_name(channel_name), status) -> "#slug" -> matches.
- modules/incident/information_update.py:311 (handle_update_field_submission) passes the raw value: update_spreadsheet_incident_status(channel_name, value), where incident_data["channel_name"] is the Slack channel name ("incident-2026-09-01-..." / "incident-dev-...") -> never matches any row -> the loop falls through and returns False.

Secondary defect: the not-found branch of update_spreadsheet_incident_status returns False with no log line, so the miss is unobservable. Every other failure branch in that function logs update_incident_spreadsheet_error.

RULED OUT - the TASK-25.1.3 Sheets migration is behaviour-equivalent (verified live, read-only):
- get_values old dispatcher vs new factory path returned identical payloads (467 rows, old == new).
- batch_update_values old vs new build an identical request URI and JSON body.
- fields=None / range=None are stripped by googleapiclient.discovery.createMethod before the request, exactly as the old filtered_params logic did.
git log also shows information_update.py's call site unchanged since well before that branch.

Note: the SlackApiError "views.update ... not_found" seen in the same log run is a separate, unrelated issue - body["view"]["root_view_id"] is stale because Slack tears down the modal stack on view_submission.

PROPOSED FIX (not urgent - see deferral note)

Normalize inside the domain function rather than at each call site. return_channel_name is idempotent ("#foo" has no incident- prefix, returned unchanged), so this fixes information_update.py without changing incident_status.py behaviour:

    sheet_name = "Sheet1"
    # Sheet stores the slug form (#slug), callers may pass the Slack channel name.
    search_value = return_channel_name(channel_name)
    ...
    for i, row in enumerate(values):
        if search_value in row:
            ...
    logger.warning(
        "update_incident_spreadsheet_error",
        channel=channel_name,
        search_value=search_value,
        status=status,
        error="Channel not found in the sheet",
    )
    return False

Tests to add in app/tests/modules/incident/test_incident_folder.py: raw "incident-dev-foo" resolves to the "#foo" row and issues the batch_update_values call; already-normalized "#foo" still matches (no regression for incident_status.py); a miss logs the warning and returns False.

DEFERRAL RATIONALE

This is deliberately not being fixed inside the TASK-25.1.3 PR, to keep that migration behaviour-neutral. It may also not be worth fixing in this shape at all: the spreadsheet is currently treated as a source of truth keyed by a fuzzy substring/membership match on a human-editable column, which is inherently flaky and risky. The intended direction is a proper DB backend as the source of truth with the spreadsheet demoted to a read-only dashboard/export. If that migration lands first, this lookup path disappears rather than being repaired. Decide between the two-line fix above and waiting for the DB-backed rewrite before scheduling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 update_spreadsheet_incident_status matches the sheet row when called with a raw Slack channel name (incident-foo / incident-dev-foo) as well as with an already-normalized #foo, and issues the batch_update_values call
- [ ] #2 A channel-not-found miss in update_spreadsheet_incident_status emits an update_incident_spreadsheet_error warning log instead of returning False silently
- [ ] #3 Regression tests in app/tests/modules/incident/test_incident_folder.py cover raw-name match, normalized-name match, and the not-found warning path
- [ ] #4 A decision is recorded (comment or decision record) on whether this lookup path is repaired as-is or removed by moving the source of truth to a DB backend with the spreadsheet demoted to a dashboard
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-01 19:28
---
Discovered while validating TASK-25.1.3 (Sheets migration off execute_google_api_call). Explicitly NOT a regression from that PR: get_values old-vs-new returned identical live payloads (467 rows, old == new) and batch_update_values old-vs-new build an identical request URI and JSON body; googleapiclient strips None kwargs exactly as the old filtered_params logic did. Left out of that PR to keep the migration behaviour-neutral.
---
<!-- COMMENTS:END -->
