---
id: TASK-22.2
title: >-
  Migrate storage service off infrastructure/clients/aws DynamoDB onto
  integrations/aws/dynamodb_next
status: To Do
assignee: []
created_date: '2026-07-29 21:10'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.1
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/infrastructure/storage/service.py
  - app/integrations/aws/dynamodb_next.py
parent_task_id: TASK-22
priority: high
ordinal: 105000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-22 (parent). Repoint infrastructure/storage/service.py off get_aws_clients().dynamodb (infrastructure/clients/aws) onto integrations/aws/dynamodb_next.

Call sites in infrastructure/storage/service.py: get_storage_service() (line ~262) resolves get_aws_clients().dynamodb and injects a DynamoDBClient into DynamoDBStorageService; the service calls self._dynamodb.put_item/get_item/delete_item/query. dynamodb_next.py exposes MODULE-LEVEL functions put_item(table_name, Item=...), get_item, update_item, delete_item, query returning OperationResult — the injection shape changes from a client object to module functions. Preserve DynamoDBStorageService's public method surface and OperationResult behavior exactly (serialize/deserialize, ConditionExpression, pagination via query force_paginate). Wire consumers to dynamodb_next as it exists today (do NOT rename the _next suffix — that is downstream TASK-23; do NOT apply the raise/classify contract — that is downstream TASK-25).

Test migration: keep storage tests in tests/unit/infrastructure/storage/ (already unit-located); ADD unit tests for the dynamodb_next path under tests/unit/integrations/aws/ (there is currently NO test_dynamodb_next). If test_client_next.py in tests/integrations/aws/ is touched, relocate it to tests/unit/integrations/aws/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/storage/service.py no longer imports infrastructure.clients.aws; DynamoDBStorageService is backed by integrations/aws/dynamodb_next
- [ ] #2 All existing tests/unit/infrastructure/storage/ tests pass with unchanged assertions (behavior-neutral); DynamoDBStorageService public methods unchanged
- [ ] #3 dynamodb_next has unit coverage under tests/unit/integrations/aws/; any touched tests/integrations/aws/ files relocated to tests/unit/integrations/aws/ (legacy tests/integrations/ file count reduced)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: storage OperationResult outcomes identical; PR references decisions/layers.md and decisions/outbound-clients.md
<!-- DOD:END -->
