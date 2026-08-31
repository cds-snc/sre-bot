---
id: TASK-23.3
title: Converge the DynamoDB retry store; delete the AWS _next dispatcher generation
status: To Do
assignee: []
created_date: '2026-08-31 17:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-23.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-23
priority: high
ordinal: 127000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Converges the DynamoDB retry store onto the canonical AWS primitive (integrations/aws/client.py::get_aws_client + classify_aws_error) and then deletes the AWS half of the _next dispatcher generation, which has no remaining consumers once this lands.

app/infrastructure/resilience/retry/dynamodb_store.py has 10 dynamodb_next call sites (put_item x1, query x4, update_item x3, delete_item x1, get_item x1).

Known latent bug fixed by this migration: dynamodb_next.query() passes force_paginate=True and keys=["Items"], so its OperationResult.data is a LIST, but fetch_due (line ~172), get_stats (~412) and get_dlq_entries (~475) all call result.data.get("Items") / .get("Count"). Those paths are broken against the real dispatcher today and only pass because the unit conftest fakes a dict-shaped result. Calling the boto3 client directly returns the dict shape the code already expects.

Scope:
1. Rewrite dynamodb_store.py's 10 call sites onto a typed boto3 client + try/except + classify_aws_error; adjust factory wiring.
2. Delete integrations/aws/dynamodb_next.py, client_next.py and identity_store_next.py (identity_store_next already has zero consumers).
3. Delete their tests and repoint the ENVIRONMENT endpoint-gate matrix test off client_next onto integrations.aws.client.

After this slice, find app/integrations -name "*_next.py" returns zero.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/resilience/retry/dynamodb_store.py imports no symbol from integrations.aws.dynamodb_next; all 10 call sites use a boto3 DynamoDB client from integrations.aws.client.get_aws_client wrapped in try/except with classify_aws_error
- [ ] #2 claim_record still returns False (not an exception) when the conditional write fails with ConditionalCheckFailedException, and still returns False and logs an error for any other classified failure
- [ ] #3 fetch_due, get_stats and get_dlq_entries are covered by tests whose fakes return the real boto3 response shape (a dict with Items / Count), proving the previously list-shaped paginated result no longer breaks them
- [ ] #4 find app/integrations -name '*_next.py' returns zero files; integrations/aws/dynamodb_next.py, client_next.py and identity_store_next.py and their tests are deleted, and the _next-generation execute_aws_api_call no longer exists (the separate non-_next execute_aws_api_call in integrations/aws/client.py stays - TASK-25.2 scope)
- [ ] #5 The ENVIRONMENT-gated dynamodb-local endpoint matrix test still covers the surviving construction path: its client_next case is repointed to integrations.aws.client.get_aws_client rather than deleted
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 mypy, ruff and pytest (excluding smoke) green from app/
- [ ] #2 Single git revert restores the previous behavior; PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->
