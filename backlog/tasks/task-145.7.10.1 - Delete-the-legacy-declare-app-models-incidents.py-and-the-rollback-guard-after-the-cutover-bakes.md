---
id: TASK-145.7.10.1
title: >-
  Delete the legacy declare, app/models/incidents.py and the rollback guard
  after the cutover bakes
status: In Progress
assignee: []
created_date: '2026-11-26T19:33:00Z'
updated_date: '2026-11-27T19:13:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.10
parent_task_id: TASK-145.7.10
ordinal: 542000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer B of the declare cutover (TASK-145.7.10 OQ1/OQ2, approved 2026-11-26): deletion only (size gate exempt), stacked directly above layer A and prepared in the same session, its PR open while A is in review. Merges only after the exit criterion (decisions/migration.md, rule added with layer A): A deployed 7 days, the post-deploy test-incident check recorded on TASK-145.7.10, no revert, at least one declare on the new path. Steps S11-S15 of TASK-145.7.10's plan. Retires dev add-incident and load-incidents early as a named change of kind (d) (migration.md:40; production refuses them outside local, modules/dev/platforms/slack.py:36-47), taken from TASK-145.12.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules/incident/incident.py, incident_alert.py, core.py and on_call.py are deleted; db_operations create_incident, update_incident_field, _read_record_version, _field_update_request and log_activity are deleted; list_incidents, get_incident_by_channel_id and lookup_incident stay for TASK-145.12.2
- [x] #2 app/models/incidents.py (Incident and IncidentPayload) and the L5r rollback guard features/incident/core/adapters/legacy_rollback.py are deleted with every TODO(TASK-145.7.10) site and their tests: tests/unit/models/test_models_incident_legacy_attribute_load.py, tests/factories/legacy_rollback.py, tests/unit/features/incident/core/test_incident_core_legacy_rollback_{view,write,round_trip}.py, tests/unit/modules/incident/test_incident_db_operations_update_field_marker.py
- [x] #3 Dev add-incident and load-incidents (modules/dev/incident.py, their registrations in modules/dev/platforms/slack.py) and incident_folder create_missing_incidents and add_new_incident_to_list are deleted with their tests; the PR body names the kind (d) change
- [x] #4 The app/pyproject.toml import-linter ignore for modules.incident.on_call, the legacy declare locale keys in app/locales/incident.*.yml (the files if nothing else reads them) and the legacy declare tests in tests/modules/incident are deleted; rg -n 'models\.incidents|legacy_rollback|TODO\(TASK-145\.7\.10\)' app returns nothing, including tests/modules/incident and tests/integration/legacy_surface
- [ ] #5 The exit criterion is recorded in the notes before merge (deploy date of layer A, the post-deploy check, no revert, a declare on the new path)
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Approved 2026-11-26 with TASK-145.7.10's plan (OQ1, OQ2): steps S11-S15 there, deletion only. Branch stack-l2/task-145.7.10.1-delete-legacy-declare above layer A. Rollback: after the exit criterion a fix-forward policy applies (migration.md rules 1, 5); B is not reverted together with A.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 prepared (18.L9b.1, stack-l2/task-145.7.10.1-delete-legacy-declare above #1900). Deletion only.
- Deleted: modules/incident/incident.py, incident_alert.py, core.py, on_call.py; models/incidents.py (Incident, IncidentPayload); features/incident/core/adapters/legacy_rollback.py (the L5r guard); db_operations create_incident, update_incident_field, _read_record_version, _field_update_request, log_activity; dev add-incident and load-incidents (modules/dev/incident.py, their registrations and catalogue keys); the app/pyproject.toml import-linter ignore for modules.incident.on_call; the legacy declare keys in app/locales/incident.*.yml (the timeline keys stay, read by incident_conversation.py); modules/__init__.py no longer imports modules.incident.incident.
- Dead after those deletions and deleted with them (no production caller left; dead-code rule): incident_folder list_incident_folders, add_new_incident_to_list, channel_id_from_link, get_incidents_from_sheet, complete_incidents_details, get_incident_details, create_missing_incidents, get_folder_metadata and IncidentSheetError; incident_conversation create_incident_conversation; incident_document create_incident_document and update_boilerplate_text; db_operations get_incident_by_channel_id and lookup_incident. AC #1 said get_incident_by_channel_id and lookup_incident stay for TASK-145.12.2: their only callers were dev add-incident and get_incident_by_channel_id, so they are dead here; list_incidents stays (dev list). Comment left on TASK-145.12.2.
- Left for Lane B: modules/slack/webhooks.py increment_acknowledged_count is dead since 18.L9b; TASK-37.6.2 deletes the acknowledged_count increments (doc-11 Lane B hand-off, 2026-11-27 (b)).
- Tests deleted: test_models_incident_legacy_attribute_load.py, factories/legacy_rollback.py, test_incident_core_legacy_rollback_{view,write,round_trip}.py, test_incident_db_operations_update_field_marker.py, tests/modules/incident/test_incident.py, test_incident_core.py, test_incident_alert.py, test_incident_on_call.py, tests/unit/modules/incident/test_incident_command_registration.py, and the parts of test_db_operations.py, test_incident_folder.py, test_incident_document.py, test_incident_conversation.py and test_dev_incident_handler.py over deleted functions. The legacy-surface conftest seeds the legacy item as a literal dict (the model is gone). The updates pin keeps only the adapter-builder recorder; baseline lines for get_incident_by_channel_id and lookup_incident deleted (legacy seams 9 -> 7). The /sre dev help pin asserts the two retired subcommands are gone.
- Named change (d): dev add-incident and load-incidents retired (migration.md:40; production refuses them outside local).
- rg -n 'models\.incidents|legacy_rollback|TODO\(TASK-145\.7\.10\)' app: empty; rg legacy_acknowledged_webhooks_seam app bin: empty.
- Docs: features/incident/README.md legacy-writer list (none left); INVENTORY rows.
- Order coupling seen in a targeted run only: tests/modules/webhooks/ run before tests/integration/legacy_surface/test_webhook_route_payload_surface.py fails 4 payload pins (blocks == []); they touch nothing this layer changes and pass alone and in the full suite's order. Reported, not fixed (Lane B's area).
- Gates: ruff check . clean; format clean; check-import-contracts 15 kept 0 broken; settings-key-ownership OK; package-shape OK (2 baselined); test-seams OK (47 strict / 7 legacy); mypy . Found 32 errors in 10 files (the session baseline less the deleted modules/incident/incident.py error; none in touched files); pytest tests --ignore=tests/smoke 8116 passed (the legacy tests removed here account for the drop from 8369).
- Exit criterion (AC #5) open: 18.L9b deployed 7 days, the post-deploy check recorded on TASK-145.7.10, no revert, one declare on the new path. The PR stays open until then.
<!-- SECTION:NOTES:END -->
