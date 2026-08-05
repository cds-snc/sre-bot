---
id: TASK-69
title: Add moto-backed DynamoDBStorageService conformance suite
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-31 16:28'
updated_date: '2026-08-04 19:57'
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
- [x] #1 New tests/integration/infrastructure/storage/test_storage_service_conformance.py exists, moto-backed via moto.mock_aws() + a real boto3 dynamodb client + a real created table, exercising DynamoDBStorageService.put/put_if_not_exists/get/query/delete against real ConditionExpression and pagination semantics
- [x] #2 Existing tests/unit/infrastructure/storage/ MagicMock-based unit tests are left unchanged (this task is additive only, not a replacement)
- [x] #3 Fixture pattern mirrors tests/integration/infrastructure/idempotency/conftest.py (pytest.importorskip guards, dummy AWS creds via monkeypatch, ENVIRONMENT=test to bypass the local/dev/ci dynamodb-local endpoint override)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (re-verified 2026-08-04, post TASK-22.2 Done): infrastructure/storage/service.py no longer depends on infrastructure.clients.aws or dynamodb_next -- DynamoDBStorageService is backed directly by integrations.aws.client.get_aws_client("dynamodb") + classify_aws_error (service.py:19-23). Its 5 public methods are put (line ~93), put_if_not_exists (line ~120, uses a real ConditionExpression `attribute_not_exists(pk)`), delete (line ~168), get (line ~193), query (line ~224, uses client.get_paginator("query") and aggregates Items across pages). get_storage_service() (line ~296, @cache) is the DI provider -- out of scope; this suite constructs DynamoDBStorageService directly, same as the existing unit tests. moto[dynamodb]>=5.2.2 is already an app/pyproject.toml:168 dependency and confirmed importable (moto 5.2.2) in the app venv. Verified against getmoto/moto's IMPLEMENTATION_COVERAGE.md (fetched 2026-08-04): dynamodb is 68% implemented with put_item, get_item, delete_item, query, scan, ConditionExpression support and paginator support all present -- fully sufficient for this suite's 5 target methods.

STEPS:
1. Create app/tests/integration/infrastructure/storage/__init__.py (empty, mirrors tests/integration/infrastructure/idempotency/__init__.py).
2. Create app/tests/integration/infrastructure/storage/conftest.py mirroring tests/integration/infrastructure/idempotency/conftest.py's dynamodb_idempotency_store fixture pattern exactly, adapted to the module storage actually depends on:
   - pytest.importorskip("moto") / pytest.importorskip("boto3") guards.
   - _set_moto_aws_credentials(monkeypatch): dummy AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SECURITY_TOKEN/AWS_SESSION_TOKEN/AWS_DEFAULT_REGION env vars via monkeypatch.setenv, plus monkeypatch.setattr(integrations.aws.client.app_settings, "ENVIRONMENT", "test") -- NOT client_next/dynamodb_next's app_settings, since storage.py imports get_aws_client from integrations.aws.client (verified service.py:19; ENVIRONMENT gate lives at integrations/aws/client.py:61-63).
   - STORAGE_TEST_TABLE_NAME = "test-sre-bot-storage-service" with KeySchema pk (HASH, S) + sk (RANGE, S) -- a composite key so query's KeyConditionExpression/pagination behavior is exercised realistically (existing idempotency table only has a single hash key).
   - Fixture `storage_service(monkeypatch)`: enters moto.mock_aws(), builds the real client via integrations.aws.client.get_aws_client("dynamodb"), creates the table, yields DynamoDBStorageService(dynamodb=client).
3. Create app/tests/integration/infrastructure/storage/test_storage_service_conformance.py, pytest.mark.integration, covering all 5 methods against real DynamoDB semantics:
   - put + get roundtrip (serialize/deserialize fidelity, including a numeric and boolean field).
   - get on a missing key returns OperationStatus.NOT_FOUND (real empty-Item response, not a mocked return value).
   - put_if_not_exists first call -> success(data=True); second call with the same pk -> success(data=False), proving the real `attribute_not_exists` ConditionExpression rejects the duplicate (this is the behavior a MagicMock cannot verify).
   - delete removes the item; a subsequent get on the same key returns NOT_FOUND.
   - query: put >=3 items sharing one pk with distinct sk values, query with KeyConditionExpression "pk = :pk", assert all items returned; repeat with Limit=1 to force multiple paginator pages and assert the paginated aggregation in query() (service.py's get_paginator("query") loop) still returns the full item set across page boundaries.
4. Do not modify anything under app/tests/unit/infrastructure/storage/ (AC#2) -- run that suite unchanged before/after to confirm zero diff in behavior.

AC-TO-STEP-TO-TEST TRACEABILITY:
- AC#1 (new conformance suite, moto-backed, real client + table, exercises put/put_if_not_exists/get/query/delete against real ConditionExpression + pagination) -> Steps 2-3; every listed test method.
- AC#2 (existing MagicMock unit tests unchanged, additive only) -> Step 4; verified via `uv run pytest tests/unit/infrastructure/storage -v` producing identical results pre/post, and via `git status` showing no modifications under tests/unit/infrastructure/storage/.
- AC#3 (fixture mirrors idempotency conftest.py: importorskip guards, dummy creds, ENVIRONMENT=test bypass) -> Step 2.

TEST MATRIX:
- put success (roundtrip); put_if_not_exists create + duplicate-rejected (real ConditionExpression); get found + get NOT_FOUND; delete + post-delete get NOT_FOUND; query single-page; query multi-page aggregation via Limit-forced pagination.
- Commands: `cd app && uv run pytest tests/integration/infrastructure/storage -v`, then `uv run pytest tests --ignore=tests/smoke`, then `uv run ruff check .` and `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`.

ASSUMPTIONS / DOUBTS (verified):
- Assumption: moto's dynamodb backend (68% implemented per getmoto/moto IMPLEMENTATION_COVERAGE.md) fully covers put_item/get_item/delete_item/query/scan + ConditionExpression + paginator -- confirmed by direct inspection of that coverage doc (fetched 2026-08-04); no gap for this suite's 5 methods.
- Doubt resolved: which app_settings module to monkeypatch ENVIRONMENT on -- integrations.aws.client.app_settings (service.py's actual dependency post-TASK-22.2), not client_next/dynamodb_next (those are separate, unrelated consumers per TASK-22.2's own scope note).
- Assumption: get_storage_service()'s @cache provider is out of scope; tests construct DynamoDBStorageService directly (matches existing unit-test convention, service.py's constructor stays injectable per TASK-22.2 AC#1).

BLAST RADIUS / ROLLBACK: purely additive -- 3 new files under app/tests/integration/infrastructure/storage/ (__init__.py, conftest.py, test_storage_service_conformance.py); zero production code changes; zero changes to any existing test file. Single git revert of the new directory fully rolls this back. No decomposition needed -- well under the single-PR size gate (new-file-only test addition, ~150-200 LOC, one subsystem).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented additive moto-backed DynamoDBStorageService conformance integration suite under app/tests/integration/infrastructure/storage with no production-code changes. Added/verified: app/tests/integration/infrastructure/storage/__init__.py, app/tests/integration/infrastructure/storage/conftest.py, app/tests/integration/infrastructure/storage/test_storage_service_conformance.py. Coverage exercises put, put_if_not_exists (real attribute_not_exists behavior), get (found + NOT_FOUND), delete, and query including paginator aggregation with Limit=1. Fixture uses pytest.importorskip for moto/boto3, dummy AWS credential env vars via monkeypatch, and ENVIRONMENT=test override on integrations.aws.client.app_settings to bypass dynamodb-local endpoint override. Existing MagicMock unit suite under app/tests/unit/infrastructure/storage was left unchanged. Evidence: uv run pytest tests/integration/infrastructure/storage -v => 7 passed; uv run pytest tests/unit/infrastructure/storage -v => 29 passed; uv run ruff check . => passed; user-reported make test => all green. Task remains In Progress for human DoD verification/closure.
<!-- SECTION:NOTES:END -->
