---
id: TASK-5.4.2
title: >-
  Access Sync: delete legacy IdempotencyService/DynamoDBCache stack now
  unreferenced
status: To Do
assignee: []
created_date: '2026-07-27 18:43'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.4.1
references:
  - decisions/reliability.md
parent_task_id: TASK-5.4
priority: high
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Contract slice of TASK-5.4, depends on TASK-5.4.1 (which migrates every access-sync call site off the legacy service). Delete app/infrastructure/idempotency/cache.py (IdempotencyCache ABC) and service.py (DynamoDBIdempotencyService) outright. Remove the DynamoDBCache class from dynamodb.py (keep DynamoDBIdempotencyStore - the TASK-5.1 claim/complete/release primitive, still used by lease.py). Remove the IdempotencyService Protocol (and its IdempotencyCache import) from protocol.py. Remove get_cache/reset_cache/get_idempotency_service and the _cache_instance singleton from factory.py (keep get_idempotency_store/build_idempotency_store/reset_idempotency_store). Prune the corresponding exports from __init__.py. Delete/update the now-obsolete tests: app/tests/unit/infrastructure/idempotency/{test_cache.py,test_dynamodb_cache.py,test_narrow_slice.py,test_idempotency_protocol.py} and app/tests/integration/infrastructure/idempotency/test_dynamodb_cache_integration.py (delete); prune conftest.py and test_factory.py's TestCacheFactory/imports. This is the final contract step that closes TASK-5's original 'delete the get-then-put path' DoD item.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/idempotency/cache.py and service.py are deleted
- [ ] #2 DynamoDBCache is removed from dynamodb.py; IdempotencyService Protocol removed from protocol.py; get_cache/reset_cache/get_idempotency_service removed from factory.py and __init__.py
- [ ] #3 grep confirms zero remaining references to IdempotencyService/DynamoDBIdempotencyService/get_cache/reset_cache/get_idempotency_service anywhere in app/
- [ ] #4 Obsolete tests for the deleted symbols are removed; remaining idempotency test suite (IdempotencyStore/lease/settings) passes unchanged
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass: full app/tests/unit and app/tests/integration idempotency suites green after deletion
- [ ] #2 PR references decisions/reliability.md and cross-references TASK-5.4.1
<!-- DOD:END -->
