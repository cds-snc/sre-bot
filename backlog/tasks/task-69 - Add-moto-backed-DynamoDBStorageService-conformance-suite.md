---
id: TASK-69
title: Add moto-backed DynamoDBStorageService conformance suite
status: To Do
assignee: []
created_date: '2026-07-31 16:28'
labels:
  - testing
  - clients
milestone: m-3
dependencies:
  - TASK-22.2
references:
  - decisions/testing.md
  - app/infrastructure/storage/service.py
  - app/tests/integration/infrastructure/idempotency/conftest.py
priority: medium
ordinal: 109000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a moto-backed integration conformance suite for DynamoDBStorageService (put/put_if_not_exists/get/query/delete), mirroring tests/integration/infrastructure/idempotency/conftest.py's dynamodb_idempotency_store fixture pattern (moto.mock_aws() + a real boto3 client + real table create), so DynamoDB-backed storage behavior (ConditionExpression semantics, pagination, deserialization) is exercised against real server-side DynamoDB semantics instead of only MagicMock-based unit tests. Scope explicitly excludes deleting/replacing the existing MagicMock-based unit tests in tests/unit/infrastructure/storage/ (those stay as fast wiring/shape tests); this adds a NEW tests/integration/infrastructure/storage/ suite alongside them, per TASK-50's own scope note (moto is for prospective new conformance suites, not mass-migrating passing tests).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New tests/integration/infrastructure/storage/test_storage_service_conformance.py exists, moto-backed via moto.mock_aws() + a real boto3 dynamodb client + a real created table, exercising DynamoDBStorageService.put/put_if_not_exists/get/query/delete against real ConditionExpression and pagination semantics
- [ ] #2 Existing tests/unit/infrastructure/storage/ MagicMock-based unit tests are left unchanged (this task is additive only, not a replacement)
- [ ] #3 Fixture pattern mirrors tests/integration/infrastructure/idempotency/conftest.py (pytest.importorskip guards, dummy AWS creds via monkeypatch, ENVIRONMENT=test to bypass the local/dev/ci dynamodb-local endpoint override)
<!-- AC:END -->
