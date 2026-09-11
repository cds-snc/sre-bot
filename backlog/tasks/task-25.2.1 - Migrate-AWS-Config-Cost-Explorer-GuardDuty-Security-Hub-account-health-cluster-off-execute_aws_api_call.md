---
id: TASK-25.2.1
title: >-
  Add characterization tests for the AWS call sites lacking unit coverage before
  adapter work
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-09-11 15:36'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - app/integrations/aws/client.py
  - app/modules/aws
  - app/modules/provisioning
  - app/modules/slack/webhooks.py
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/jobs/scheduled_tasks.py
  - app/jobs/revoke_aws_sso_access.py
parent_task_id: TASK-25.2
priority: high
ordinal: 118000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 0 of TASK-25.2 (tests-only gate, mirrors TASK-25.1.6.1). Before adapters replace the False-swallowing integrations/aws mirrors, lock the current observable behaviour of each legacy call site, including what the caller does when the integration returns False today, so the switch to OperationResult in later slices shows up as an explicit, reviewable diff rather than a silent behaviour change.

Known coverage state (2026-09-11, starting point only; the planner re-greps it): tests/unit/modules/aws/* cover aws_access_requests, aws_account_health, identity_center, lambdas, ops_group_assignment and spending handlers; tests/unit/jobs/test_revoke_aws_sso_access.py exists; tests/unit/modules/provisioning has test_provisioning_users.py only (groups is covered by the legacy tests/modules/provisioning suite); modules/slack/webhooks.py and modules/incident/{db_operations,incident_folder}.py are covered only by legacy tests/modules suites and the webhooks e2e; jobs/scheduled_tasks.py's identity_store.healthcheck path and modules/aws/aws.py's get_user_id / get_account_id_by_name path have no targeted test.

Production code is not modified. New tests go under app/tests/ per the testing-standards skill, named test_<domain>_<entity>_<action>.py, with docstrings describing observable behaviour and stub strategy only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every production call into integrations.aws.{identity_store,organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas,dynamodb} has at least one unit test asserting the caller's success path and its behaviour when the integration returns False; the verified call-site inventory is recorded in notes
- [ ] #2 No production file is modified; ruff, mypy and pytest pass with output recorded
<!-- AC:END -->
