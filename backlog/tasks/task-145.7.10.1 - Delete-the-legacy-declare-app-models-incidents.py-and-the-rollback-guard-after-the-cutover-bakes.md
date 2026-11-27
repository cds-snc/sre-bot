---
id: TASK-145.7.10.1
title: >-
  Delete the legacy declare, app/models/incidents.py and the rollback guard
  after the cutover bakes
status: To Do
assignee: []
created_date: '2026-11-26T19:33:00Z'
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
- [ ] #1 modules/incident/incident.py, incident_alert.py, core.py and on_call.py are deleted; db_operations create_incident, update_incident_field, _read_record_version, _field_update_request and log_activity are deleted; list_incidents, get_incident_by_channel_id and lookup_incident stay for TASK-145.12.2
- [ ] #2 app/models/incidents.py (Incident and IncidentPayload) and the L5r rollback guard features/incident/core/adapters/legacy_rollback.py are deleted with every TODO(TASK-145.7.10) site and their tests: tests/unit/models/test_models_incident_legacy_attribute_load.py, tests/factories/legacy_rollback.py, tests/unit/features/incident/core/test_incident_core_legacy_rollback_{view,write,round_trip}.py, tests/unit/modules/incident/test_incident_db_operations_update_field_marker.py
- [ ] #3 Dev add-incident and load-incidents (modules/dev/incident.py, their registrations in modules/dev/platforms/slack.py) and incident_folder create_missing_incidents and add_new_incident_to_list are deleted with their tests; the PR body names the kind (d) change
- [ ] #4 The app/pyproject.toml import-linter ignore for modules.incident.on_call, the legacy declare locale keys in app/locales/incident.*.yml (the files if nothing else reads them) and the legacy declare tests in tests/modules/incident are deleted; rg -n 'models\.incidents|legacy_rollback|TODO\(TASK-145\.7\.10\)' app returns nothing, including tests/modules/incident and tests/integration/legacy_surface
- [ ] #5 The exit criterion is recorded in the notes before merge (deploy date of layer A, the post-deploy check, no revert, a declare on the new path)
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Approved 2026-11-26 with TASK-145.7.10's plan (OQ1, OQ2): steps S11-S15 there, deletion only. Branch stack-l2/task-145.7.10.1-delete-legacy-declare above layer A. Rollback: after the exit criterion a fix-forward policy applies (migration.md rules 1, 5); B is not reverted together with A.
<!-- SECTION:PLAN:END -->
