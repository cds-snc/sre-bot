---
id: TASK-25.2.5.3
title: >-
  Migrate incident persistence (db_operations.py, incident_folder.store_update)
  onto the DynamoDB adapter
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.5.1
references:
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/tests/modules/incident/test_db_operations.py
  - app/tests/modules/incident/test_incident_folder.py
parent_task_id: TASK-25.2.5
priority: high
ordinal: 216000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 (migrate) of TASK-25.2.5. Moves modules/incident/db_operations.py (162 LOC) and incident_folder.py's store_update off integrations.aws.dynamodb onto build_dynamodb_adapter(). One subsystem: both write the "incidents" table. Downstream callers are unchanged: modules/incident/{core,incident_helper,incident_status,information_display,information_update,incident_folder}.py and modules/dev/incident.py.

Call sites (read 2026-09-15):
- create_incident :40 put_item. Today it indexes response["ResponseMetadata"], so it crashes on False (TASK-25.2.1 item 33).
- list_incidents :67 scan (item 34)
- update_incident_field :90 update_item "SET #f = :f" (item 35)
- log_activity :108 update_item "SET logs = list_append(...)" (item 36)
- get_incident :138 get_item (item 37)
- lookup_incident :158 scan, reached from get_incident_by_channel_id :141, whose len() crashes on False (item 38)
- incident_folder.store_update :546 update_item "SET incident_updates = :updates". Today .get() on False crashes (item 39).

Error policy (human decisions 2026-09-15, shared with .2):
- list_incidents and lookup_incident: a non-success result logs status/error_code/error and raises RuntimeError; an empty scan still returns []. Effect: get_incident_by_channel_id stops crashing, and create_incident's duplicate check (plus core.py, incident_helper.py and create_missing_incidents) never treats a failed scan as "no incident", which today can create a duplicate record.
- create_incident, update_incident_field and store_update keep their existing failure branches: log and return None.
- log_activity is not replay-safe (list_append duplicates the entry), so it is sent with update_item(retries=False). On non-success it keeps returning False with its error log.
- Raised (unclassified) errors propagate (TASK-25.2.4.x precedent).
- get_incident is dropped after a re-grep confirms zero production callers.
- store_update's read-modify-write race and fetch_updates are out of scope (TASK-38).
- incident_folder.py drops its integrations.aws import; nothing else in it changes.

Tests: tests/modules/incident/test_db_operations.py and test_incident_folder.py keep their legacy names. The adapter is mocked with MagicMock(spec=DynamoDBAdapter) returning OperationResult. The pinned tests (test_db_operations.py :209-:264, test_incident_folder.py :476) are replaced by tests of the new behaviour, and get_incident's tests are removed with it.

Overlap: TASK-38 later moves incident persistence into packages/incident/common, so keep the diff minimal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/incident/db_operations.py and incident_folder.py no longer import integrations.aws.dynamodb and reach DynamoDB only through build_dynamodb_adapter() called at function entry
- [ ] #2 list_incidents and lookup_incident log status, error_code and error and raise on a non-success result, so get_incident_by_channel_id and create_incident's duplicate check never treat a failed scan as no incident; empty scans still return []
- [ ] #3 create_incident, update_incident_field and store_update log and return None on a non-success write; log_activity calls update_item(retries=False) and returns False with an error log on a non-success result
- [ ] #4 get_incident is deleted after a re-grep confirms no production caller; the pinned False-return tests are replaced by tests of the new behaviour
- [ ] #5 Per-call-site before/after error-path behaviour is recorded in notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->
