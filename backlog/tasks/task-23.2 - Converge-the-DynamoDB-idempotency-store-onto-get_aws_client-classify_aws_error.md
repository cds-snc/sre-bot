---
id: TASK-23.2
title: >-
  Converge the DynamoDB idempotency store onto get_aws_client +
  classify_aws_error
status: To Do
assignee: []
created_date: '2026-08-31 17:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-23
priority: high
ordinal: 126000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Converges the DynamoDB idempotency store off the _next dispatcher onto the canonical AWS primitive shipped by TASK-22.2 (integrations/aws/client.py::get_aws_client + classify_aws_error), following the DynamoDBStorageService shape.

Today app/infrastructure/idempotency/dynamodb.py imports get_item/put_item/delete_item from integrations.aws.dynamodb_next, which routes through client_next.execute_aws_api_call (string dispatch + hand-rolled time.sleep retry) and returns OperationResult.

Scope: rewrite DynamoDBIdempotencyStore to hold a typed boto3 DynamoDB client and wrap each call in try/except + classify_aws_error; wire client construction through infrastructure/idempotency/factory.py; repoint the moto-backed conformance conftest off integrations.aws.client_next.

integrations/aws/dynamodb_next.py is NOT deleted here - the resilience retry store still consumes it until TASK-23.3.

Critical invariant: claim() branches on error_code == "ConditionalCheckFailedException" as its contention signal. classify_aws_error already maps that code to PERMANENT_ERROR with the code preserved; the claim/complete/release outcomes must be identical before and after.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/idempotency/dynamodb.py imports no symbol from integrations.aws.dynamodb_next; it holds a boto3 DynamoDB client obtained via integrations.aws.client.get_aws_client and wraps every call in try/except with integrations.aws.client.classify_aws_error
- [ ] #2 claim/complete/release outcomes are unchanged: a conditional-write failure still yields ClaimResult.IN_PROGRESS or COMPLETED via the ConditionalCheckFailedException error_code, and a COMPLETED record still returns its stored outcome payload
- [ ] #3 The moto-backed conformance suite under tests/integration/infrastructure/idempotency passes without importing integrations.aws.client_next; its ENVIRONMENT override targets integrations.aws.client instead
- [ ] #4 Unit tests cover the three claim outcomes, complete, release, and one unmapped SDK exception propagating rather than being swallowed into a permanent error
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 mypy, ruff and pytest (excluding smoke) green from app/
- [ ] #2 Single git revert restores the previous behavior; PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->
