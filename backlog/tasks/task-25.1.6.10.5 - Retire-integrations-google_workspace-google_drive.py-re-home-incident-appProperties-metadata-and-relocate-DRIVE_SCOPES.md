---
id: TASK-25.1.6.10.5
title: >-
  Retire integrations/google_workspace/google_drive.py: re-home incident
  appProperties metadata and relocate DRIVE_SCOPES
status: To Do
assignee: []
created_date: '2026-09-09 15:04'
updated_date: '2026-09-09 15:29'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.10.1
  - TASK-25.1.6.13
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/integrations/google_workspace/google_drive.py
  - app/packages/incident/drive/adapters/google_drive.py
  - app/infrastructure/drive/google.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.6.10
priority: medium
ordinal: 163000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Take app/integrations/google_workspace/google_drive.py to zero production references and delete it. This inherits TASK-25.1.6.10's original AC#7, whose premise ('its last two call sites live in modules/reports/google_groups.py') is stale - see the 2026-09-08 impact note on the parent.

ACTUAL REMAINING REFERENCES after TASK-25.1.6.10.1 deletes modules/reports (grep-verified 2026-09-09):
1. app/packages/incident/drive/adapters/google_drive.py - deliberate temporary pass-throughs shipped by TASK-25.1.6.8.2: add_metadata, delete_metadata, get_metadata (via legacy list_metadata), and find_document_by_channel_name's metadata lookup. These are Google appProperties operations, intentionally excluded from the vendor-neutral DriveProvider by the 2026-09-08 architecture clarification recorded on TASK-25.1.6.8.1 and in decisions/layers.md.
2. app/infrastructure/drive/google.py:13 imports DRIVE_SCOPES from it.
3. app/packages/incident_draft/adapters/google_docs.py:321 and :1308 use google_drive.DRIVE_SCOPES.

WHY THIS IS A SEPARATE SLICE, NOT PART OF THE SHEETS MIGRATION: it is Drive-shaped work with its own architectural decision (where Google appProperties lives), and it was only parked on TASK-25.1.6.10 because the deleted report module used to hold the last call sites. Kept under this coordinator because .10 already owned the deletion; nothing in it depends on the spreadsheets capability.

TARGET SHAPE:
- The three metadata operations become REAL Path B code inside packages/incident/drive/adapters/google_drive.py, per decisions/layers.md ('the feature adapter owns vendor-specific behavior during migration') and decisions/outbound-clients.md ('the adapter is the boundary'): build the Resource from integrations.google_workspace.client.get_drive_service, call files().get / files().update(body={'appProperties': ...}) with supportsAllDrives=True directly on the stub-typed handle, wrap in try/except HttpError, and classify with classify_google_error. No execute_google_api_request, no pass-through to a vendor mirror module. The adapter keeps returning the dict shapes its incident callers consume today, so no consumer outside the adapter changes.
- DRIVE_SCOPES relocates into app/infrastructure/drive/google.py (scopes are Google-specific and belong in the Google implementation, the same rule TASK-25.1.6.10.2 applies to the Sheets scope from the start). infrastructure/drive/google.py drops the cross-tier import into a doomed vendor module - the wart flagged as step 5B / doubt (b) on TASK-25.1.6.8.1. packages/incident_draft/adapters/google_docs.py and the incident Drive adapter take the constant from its new home, or define their own if the incident_draft adapter's scope needs differ.
- app/integrations/google_workspace/google_drive.py and app/tests/integrations/google_workspace/test_google_drive.py are deleted.

WATCH: app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py asserts on the string 'integrations.google_workspace import google_drive' in the adapter source. That guard must be updated to match the new boundary (the adapter will legitimately import integrations.google_workspace.client instead, which decisions/layers.md permits only inside adapters/), not deleted.

NOT IN SCOPE: widening DriveProvider with metadata methods (explicitly rejected 2026-09-08 - appProperties is not a portable capability), LEGACY_FOLDER_DISPLAY_LIMIT (TASK-81), any Sheets work, and the deletion of execute_google_api_request (TASK-25.1.6.11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident/drive/adapters/google_drive.py implements add_metadata, delete_metadata and get_metadata itself against a stub-typed DriveResource from integrations.google_workspace.client.get_drive_service, with its own try/except HttpError plus classify_google_error; no pass-through to a vendor mirror module and no execute_google_api_request remains
- [ ] #2 infrastructure.drive.DriveProvider is NOT widened with metadata or appProperties operations; the vendor-neutral contract is unchanged
- [ ] #3 DRIVE_SCOPES lives in app/infrastructure/drive/google.py (or each adapter owns its own scope list); no module imports it from integrations.google_workspace.google_drive, including packages/incident_draft/adapters/google_docs.py's two call sites
- [ ] #4 app/integrations/google_workspace/google_drive.py and app/tests/integrations/google_workspace/test_google_drive.py are deleted, with zero remaining production references repo-wide
- [ ] #5 app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py is updated to guard the new boundary rather than deleted, and the incident callers of the metadata functions are unchanged
- [ ] #6 Unit tests cover the three metadata operations' success and classified-failure paths at the adapter's SDK seam
- [ ] #7 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 15:29
---
RETRY CONSTRAINT ADDED 2026-09-09 (human-directed, from TASK-25.1.6.10.2's review). Your new Path B metadata code in packages/incident/drive/adapters/google_drive.py calls the SDK directly, so it would otherwise be the next place a per-call retry argument gets sprinkled.

DO NOT PASS num_retries AT ANY .execute() CALL AND DO NOT DEFINE A RETRY CONSTANT. Retry is configured once at construction in integrations/google_workspace/client.py by TASK-25.1.6.13, now a dependency of this task. Verified against google-api-python-client 2.198.0: build(num_retries=N) only retries the discovery-document fetch, while build(requestBuilder=...) is the real construction-time seam - so the configuration genuinely belongs in client.py, not at your call sites.

NOTE FOR YOUR PLANNING: TASK-25.1.6.13 also deletes _NUM_RETRIES and the 12 per-call num_retries arguments from infrastructure/directory/google.py and infrastructure/drive/google.py. If you read infrastructure/drive/google.py as a template while writing the metadata adapter, read it AFTER .13 lands, or you will copy a shape that is being removed.
---
<!-- COMMENTS:END -->
