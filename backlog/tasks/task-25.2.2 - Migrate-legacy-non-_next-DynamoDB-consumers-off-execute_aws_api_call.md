---
id: TASK-25.2.2
title: Migrate legacy (non-_next) DynamoDB consumers off execute_aws_api_call
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-08-04 19:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/dynamodb.py
parent_task_id: TASK-25.2
priority: high
ordinal: 119000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.2. Migrate integrations/aws/dynamodb.py (a THIRD, older DynamoDB generation, distinct from both the deprecated facade and dynamodb_next.py) off execute_aws_api_call/handle_aws_api_errors, reusing get_aws_client("dynamodb") + classify_aws_error already built in TASK-22.2 directly (do not build a second DynamoDB primitive). Production consumers (grep-confirmed 2026-07-31): modules/incident/incident_folder.py, modules/incident/db_operations.py, modules/slack/webhooks.py. Also hardcodes its own ENVIRONMENT in (local,dev,ci) -> http://dynamodb-local:8000 endpoint gate (matches the convention TASK-22.2 already reconciled for dynamodb_next - reuse the same gate, do not reintroduce a third copy). Same silent-False-swallow caveat as sibling slices: must convert to raise+classify explicitly, human-reviewed, not zero-diff.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/dynamodb.py no longer calls execute_aws_api_call/handle_aws_api_errors; routes through the SAME get_aws_client("dynamodb")/classify_aws_error instance TASK-22.2 built for infrastructure/storage (not a new one)
- [ ] #2 modules/incident/incident_folder.py, modules/incident/db_operations.py, and modules/slack/webhooks.py are updated to the raise+classify contract explicitly; resulting error-path behavior documented and human-reviewed
- [ ] #3 integrations/aws/dynamodb.py's hardcoded dynamodb-local endpoint gate is removed in favor of the single shared gate from TASK-22.2 (no duplicate ENVIRONMENT-check copies remain)
- [ ] #4 moto-backed integration conformance test(s) under app/tests/integration/ exercise integrations/aws/dynamodb.py's query/scan/put_item/get_item/update_item/delete_item against real DynamoDB semantics via moto.mock_aws() (reuse/extend the TASK-69 conformance fixture pattern for the same get_aws_client("dynamodb") primitive rather than building a second one), additive alongside existing MagicMock-based unit tests
<!-- AC:END -->
