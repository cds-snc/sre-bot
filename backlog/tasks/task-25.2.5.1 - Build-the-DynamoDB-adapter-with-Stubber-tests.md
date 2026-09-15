---
id: TASK-25.2.5.1
title: Build the DynamoDB adapter with Stubber tests
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - app/packages/aws_platform/adapters/aws_lambda.py
  - app/packages/aws_platform/adapters/identity_center.py
  - app/integrations/aws/client.py
  - app/integrations/aws/dynamodb.py
  - app/.env.example
parent_task_id: TASK-25.2.5
priority: high
ordinal: 214000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 (expand) of TASK-25.2.5. No caller changes.

Create app/packages/aws_platform/adapters/dynamodb.py in the shape landed by TASK-25.2.4.2 (aws_lambda.py) and TASK-25.2.3.1 (identity_center.py, two clients):
- DynamoDBAdapter(client, client_no_retry) holds two types_boto3 DynamoDBClient handles. _map_sdk_exception/_call are copied privately, as siblings do (no shared base). Only ClientError/BotoCoreError are classified with classify_aws_error; anything else propagates.
- build_dynamodb_adapter() builds get_aws_client("dynamodb") and get_aws_client("dynamodb", retries=False) in-account, with no SERVICE_ROLE_MAP entry and no AssumeRole. Callers build it at function entry, never at import.
- Operations, limited to what TASK-25.2.5.2/.3 call (re-grep first):
  - scan(**kwargs) -> OperationResult[list[dict]] through get_paginator("scan"), with every page's Items flattened. Callers pass FilterExpression/ExpressionAttributeValues/Select.
  - get_item(**kwargs) -> OperationResult[dict | None]: success with the Item, or data=None when absent. A missing item is not an error.
  - put_item(**kwargs) -> OperationResult[None]
  - update_item(*, retries: bool = True, **kwargs) -> OperationResult[None]. retries=False sends the call on the retries-disabled client, for writes that are not replay-safe (decisions/outbound-clients.md item 25).
- Request kwargs keep the low-level AttributeValue shapes and are typed with the types_boto3_dynamodb TypedDicts (ScanInputPaginateTypeDef, GetItemInputTypeDef, PutItemInputTypeDef, UpdateItemInputTypeDef) via Unpack, if mypy accepts it. Otherwise use dict[str, Any] and record why.
- Not ported (no caller after .2/.3; re-grep): query, delete_item, list_tables.

Local endpoint: the client applies AWS_ENDPOINT_URL_DYNAMODB (integrations/aws/settings.py DYNAMODB_ENDPOINT_URL, set in .devcontainer/docker-compose.yml). This replaces the legacy ENVIRONMENT in (local, dev, ci) gate. app/.env.example still shows a commented generic AWS_ENDPOINT_URL. Rename it to AWS_ENDPOINT_URL_DYNAMODB so local setups outside the devcontainer keep reaching dynamodb-local once callers move.

Tests (Stubber, the TASK-25.2.4 human decision): tests/unit/packages/aws_platform/test_aws_platform_dynamodb_operations.py and test_aws_platform_dynamodb_provider.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/dynamodb.py exposes scan, get_item, put_item and update_item returning OperationResult with AttributeValue request/response shapes unchanged; ClientError/BotoCoreError are classified via classify_aws_error and any other exception propagates
- [ ] #2 scan returns the Items of every page flattened through get_paginator('scan'); get_item returns success with data None when the item is absent
- [ ] #3 update_item(retries=False) is sent on the retries-disabled client and every other call on the retrying client; build_dynamodb_adapter builds both only through get_aws_client('dynamodb') with no role ARN
- [ ] #4 Stubber tests cover success, multi-page scan, absent item, each mapped error family, the retries routing and one unmapped exception propagating; a provider test covers build_dynamodb_adapter
- [ ] #5 app/.env.example names AWS_ENDPOINT_URL_DYNAMODB; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with commands and output recorded in notes
<!-- AC:END -->
