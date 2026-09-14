---
id: TASK-25.2.5
title: >-
  Build the DynamoDB adapter for legacy callers and migrate webhooks and
  incident persistence; delete integrations/aws/dynamodb.py
status: To Do
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-14 14:08'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4
references:
  - app/integrations/aws/dynamodb.py
  - app/modules/slack/webhooks.py
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/infrastructure/idempotency/dynamodb.py
  - app/infrastructure/storage/service.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.2. Create packages/aws_platform/adapters/dynamodb.py: a thin adapter over the typed dynamodb client from get_aws_client("dynamodb") that keeps the low-level AttributeValue request/response shapes legacy callers use today (query, scan, put_item, get_item, update_item, delete_item, list_tables), paginates through client.get_paginator, and returns OperationResult. DynamoDBStorageService is deliberately not adopted by these callers here (human decision 2026-09-11); a later feature migration may switch them.

Callers migrated (starting list, re-grep before planning): modules/slack/webhooks.py, modules/incident/db_operations.py, modules/incident/incident_folder.py. modules/aws/aws_access_requests.py was removed from this list on 2026-09-14 (human decision). It built its own boto3.client("dynamodb") with a hardcoded local endpoint, but it belongs to the dead AWS account access-request flow, which is deleted under TASK-25.2.3.2.4 with no code parity. Its boto3 construction disappears with it, and no migration is needed here.

Retry safety: audit every update_item whose expression is not idempotent under replay (ADD counters, list appends) and route those through the retries-disabled factory option or a condition expression, per decisions/outbound-clients.md item 25.

Also in scope (from the earlier TASK-25.2 comment): reassess the classify-and-continue downgrade in infrastructure/idempotency/dynamodb.py, where a classified SDK failure while re-reading a contended claim becomes ClaimResult.IN_PROGRESS, together with any other classify-and-continue site found on the DynamoDB paths; decide raise vs keep per site and record the decision.

Deleted: integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py (endpoint-gate coverage moves to the client.py tests if not already there; its aws_access_requests case is already removed by TASK-25.2.3.2.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/dynamodb.py returns OperationResult for each operation, keeps AttributeValue shapes, builds its client only through get_aws_client, and has Stubber unit tests
- [ ] #2 webhooks.py, incident db_operations.py and incident_folder.py use the adapter; no boto3.client or boto3.Session construction remains in production code outside integrations/aws/client.py
- [ ] #3 Non-idempotent update_item sites are inventoried and each either uses the retries-disabled option or a conditional write, with the inventory in notes
- [ ] #4 The idempotency-store classify-and-continue downgrade is reassessed with a recorded decision and a matching test
- [ ] #5 integrations/aws/dynamodb.py and its legacy tests are deleted; both guard baselines pruned
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:05
---
2026-09-14 (human decision): modules/aws/aws_access_requests.py was removed from the caller list and from AC#2. It is dead in production and is deleted under TASK-25.2.3.2.4 with no code parity. The frontmatter reference to it is historical.
---

created: 2026-09-14 14:08
---
2026-09-14: title no longer mentions access-request persistence, and the aws_access_requests.py frontmatter reference was removed, following the re-scope above.
---
<!-- COMMENTS:END -->
