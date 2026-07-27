---
id: TASK-5.4.2
title: >-
  Access Sync: delete legacy IdempotencyService/DynamoDBCache stack now
  unreferenced
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-27 18:43'
updated_date: '2026-07-27 20:39'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposition context: this is the contract half of the TASK-5.4 expand/migrate/contract split (TASK-5.4 -> TASK-5.4.1 expand+migrate [Done] / TASK-5.4.2 this task, delete). TASK-5.4.1 confirmed Done: all app/packages/access/sync call sites (job_runner.py, interactions/http.py, interactions/slack.py, interactions/ingress.py, platform_lock.py) migrated onto the new package-owned JobStatusStore; repo-wide grep (excluding .mypy_cache/.pytest_cache) confirms zero remaining references to IdempotencyService/DynamoDBIdempotencyService/get_cache/reset_cache/get_idempotency_service/IdempotencyCache/DynamoDBCache outside app/infrastructure/idempotency/* itself and its own tests. This slice is pure deletion of now-dead code plus its obsolete tests - no new logic, single subsystem (infrastructure/idempotency), well under the single-PR size gate despite touching about 13 files (2 prod deletions + 4 small prod edits removing code; 5 test deletions + 1 test edit + 1 test-conftest deletion, all subtractive).

## Grounding (current state, confirmed 2026-07-27)

Production files in app/infrastructure/idempotency/:
- cache.py: only IdempotencyCache ABC (get/set/clear/get_stats) - entirely superseded by IdempotencyStore Protocol. DELETE.
- service.py: only DynamoDBIdempotencyService (wraps IdempotencyCache) - entirely superseded. DELETE.
- dynamodb.py: contains BOTH DynamoDBIdempotencyStore (TASK-5.1 primitive, keep - still used by lease.py/JobStatusStore-adjacent callers) AND DynamoDBCache(IdempotencyCache) (legacy, delete). Also imports scan from integrations.aws.dynamodb_next, used only by DynamoDBCache.clear() - becomes unused once DynamoDBCache is removed, must also be dropped from the import line.
- protocol.py: contains BOTH IdempotencyStore Protocol + ClaimResult/ClaimOutcome (keep) AND IdempotencyService Protocol (legacy, delete), plus an import of IdempotencyCache from cache.py used only by IdempotencyService's cache property type hint - drop that import too.
- factory.py: contains BOTH get_idempotency_store/build_idempotency_store/reset_idempotency_store/_idempotency_store_instance (keep) AND get_cache/reset_cache/get_idempotency_service/_cache_instance (legacy, delete). Imports to drop: IdempotencyCache (cache.py), DynamoDBCache (dynamodb.py), IdempotencyService (protocol.py), DynamoDBIdempotencyService (service.py). Keep DynamoDBIdempotencyStore, IdempotencyStore, IdempotencySettings/get_idempotency_settings imports.
- __init__.py: exports both stacks; module docstring's usage example still shows get_cache()/cache.get(...)/cache.set(...) - must be rewritten (dangling reference to a symbol this task deletes), not just the __all__ list.

Repo-wide grep (app/packages, app/infrastructure, app/api, app/server, app/integrations, app/jobs, app/modules, app/tests, plus decisions/docs/terraform/backlog) for IdempotencyService, DynamoDBIdempotencyService, get_cache(, reset_cache(, get_idempotency_service, IdempotencyCache, DynamoDBCache confirms ALL remaining hits are either (a) inside app/infrastructure/idempotency/* itself (the files this task edits/deletes), (b) inside the test files this task deletes/prunes, (c) historical prose in backlog/tasks/task-5*.md (CLI-owned, out of scope, describes already-completed history), or (d) one stale illustrative code snippet in the legacy docs/adr/dependency-injection.md line 155 (pre-migration Tier-2 doc, superseded by decisions/ per the two-decision-tree state noted in repo memory - out of this task's scope, flagged below as an assumption not a blocker).

Test files (app/tests/unit/infrastructure/idempotency/ and app/tests/integration/infrastructure/idempotency/):
- test_cache.py: tests IdempotencyCache ABC only. DELETE.
- test_dynamodb_cache.py: tests DynamoDBCache only (uses conftest.py's mock_settings fixture). DELETE.
- test_narrow_slice.py: tests DynamoDBCache + DynamoDBIdempotencyService construction/DI shape only. DELETE.
- test_idempotency_protocol.py: tests the legacy IdempotencyService Protocol only (FakeIdempotencyCache/FakeIdempotencyService helpers, DynamoDBIdempotencyService). DELETE.
- app/tests/integration/infrastructure/idempotency/test_dynamodb_cache_integration.py: tests DynamoDBCache against moto only. DELETE. (Sibling test_idempotency_store_conformance.py and its conftest.py already reference only DynamoDBIdempotencyStore/InMemoryIdempotencyStore - untouched, no cache references present.)
- test_factory.py: has TWO classes - TestCacheFactory (get_cache/reset_cache, DELETE this class) and TestIdempotencyStoreFactory plus test_build_idempotency_store_overrides_in_progress_ttl_only (keep, unrelated to cache). Also drop the now-unused get_cache, reset_cache import from infrastructure.idempotency and DynamoDBCache from infrastructure.idempotency.dynamodb (keep DynamoDBIdempotencyStore).
- conftest.py (unit dir): defines mock_settings/sample_response/operation_result_success/operation_result_failure/mock_dynamodb_cache fixtures (used ONLY by the 4 test files being deleted above - confirmed via grep, zero other usages in test_dynamodb_store.py/test_idempotency_settings.py/test_idempotency_store_protocol.py/test_in_memory_store.py/test_lease.py, which all define their own local fixtures) plus an autouse reset_cache_singleton fixture that imports and calls reset_cache() from factory.py - this autouse fixture runs for EVERY test in the directory today, so once reset_cache is deleted from factory.py this file would break collection for the entire directory, not just cache tests, unless pruned. Since every fixture in this file becomes dead once the 4 cache test files are deleted, DELETE the whole conftest.py rather than leaving an empty shell (see Assumptions below - flagged as a prune-to-zero judgment call, not literally renaming/emptying).

## Ordered steps

1. Delete app/tests/unit/infrastructure/idempotency/test_cache.py, test_dynamodb_cache.py, test_narrow_slice.py, test_idempotency_protocol.py.
2. Delete app/tests/integration/infrastructure/idempotency/test_dynamodb_cache_integration.py.
3. Delete app/tests/unit/infrastructure/idempotency/conftest.py (all fixtures dead after step 1; verified zero remaining consumers in the directory).
4. Edit app/tests/unit/infrastructure/idempotency/test_factory.py: remove the TestCacheFactory class and its docstring; remove get_cache, reset_cache from the infrastructure.idempotency import line (drop the line entirely if nothing else is imported from it); remove DynamoDBCache from the infrastructure.idempotency.dynamodb import line, keep DynamoDBIdempotencyStore. Keep TestIdempotencyStoreFactory and test_build_idempotency_store_overrides_in_progress_ttl_only unchanged.
5. Delete app/infrastructure/idempotency/cache.py.
6. Delete app/infrastructure/idempotency/service.py.
7. Edit app/infrastructure/idempotency/dynamodb.py: remove the DynamoDBCache class entirely; remove the IdempotencyCache import from cache.py; remove scan from the integrations.aws.dynamodb_next import line (keep delete_item, get_item, put_item). Keep DynamoDBIdempotencyStore and its imports (json, time, Any, structlog, ClaimOutcome/ClaimResult/IdempotencyStore, IdempotencySettings) unchanged.
8. Edit app/infrastructure/idempotency/protocol.py: remove the IdempotencyService Protocol class entirely; remove the IdempotencyCache import from cache.py. Keep ClaimResult, ClaimOutcome, IdempotencyStore unchanged.
9. Edit app/infrastructure/idempotency/factory.py: remove get_cache, reset_cache, get_idempotency_service, and the _cache_instance module global; remove now-unused imports (IdempotencyCache from cache.py, DynamoDBCache from dynamodb.py, IdempotencyService from protocol.py, DynamoDBIdempotencyService from service.py). Keep get_idempotency_store, build_idempotency_store, reset_idempotency_store, _idempotency_store_instance, and their imports (DynamoDBIdempotencyStore, IdempotencyStore, IdempotencySettings/get_idempotency_settings) unchanged.
10. Edit app/infrastructure/idempotency/__init__.py: remove IdempotencyCache, DynamoDBCache, get_cache, reset_cache, get_idempotency_service, DynamoDBIdempotencyService from both the import statements and __all__. Rewrite the module docstring's usage example to demonstrate the current IdempotencyStore claim/complete/release contract (or get_idempotency_store()) instead of the deleted get_cache()/cache.get/cache.set example, so no dangling reference to a removed symbol remains in the file's own documentation.
11. Verification (run before considering AC#3/#4 satisfied):
    a. grep for IdempotencyService, DynamoDBIdempotencyService, get_cache, reset_cache, get_idempotency_service, IdempotencyCache, DynamoDBCache across app/ (excluding .mypy_cache/.pytest_cache build artifacts) returns empty.
    b. cd app; uv run pytest tests/unit/infrastructure/idempotency tests/integration/infrastructure/idempotency -v all green.
    c. cd app; uv run mypy . --exclude the .venv path, and uv run ruff check . clean (catches unused imports from the surgical edits in steps 7-10).
    d. cd app; uv run pytest tests --ignore=tests/smoke full suite green (confirms no other package accidentally depended on a deleted symbol beyond what step-grounding already found).

## AC traceability

- AC#1 (cache.py/service.py deleted) <- steps 5-6.
- AC#2 (DynamoDBCache removed from dynamodb.py; IdempotencyService Protocol removed from protocol.py; get_cache/reset_cache/get_idempotency_service removed from factory.py and __init__.py) <- steps 7, 8, 9, 10.
- AC#3 (grep confirms zero remaining references anywhere in app/) <- step 11a.
- AC#4 (obsolete tests removed; remaining idempotency suite passes unchanged) <- steps 1-4 (removal) plus step 11b (green run). Unchanged is verified by diffing test outcomes for the 5 untouched files (test_dynamodb_store.py, test_idempotency_settings.py, test_idempotency_store_protocol.py, test_in_memory_store.py, test_lease.py) plus test_factory.py (pruned) and test_idempotency_store_conformance.py - same pass count/assertions, no behavior change, only fixture-source removal.

## Test matrix

No new tests are authored by this task (pure deletion/contraction). Verification is regression-only:
- Unit: app/tests/unit/infrastructure/idempotency test_dynamodb_store.py, test_idempotency_settings.py, test_idempotency_store_protocol.py, test_in_memory_store.py, test_lease.py, test_factory.py (pruned) must all pass unchanged after steps 1-10.
- Integration: app/tests/integration/infrastructure/idempotency/test_idempotency_store_conformance.py must pass unchanged (its conftest.py already has zero cache references, confirmed by direct read - no edit needed).
- Full-repo regression: app/tests, ignoring tests/smoke, to catch any caller outside the idempotency package/tests that repo-wide grep might have missed (defense in depth, cost is low - full suite already run as a standing validation-policy step).

## Assumptions and doubts

- Deleting (not merely emptying) app/tests/unit/infrastructure/idempotency/conftest.py: the task description says prune conftest.py, which could be read as edit it down rather than delete the file. Verified via grep that all 6 fixtures it defines (mock_settings, sample_response, operation_result_success, operation_result_failure, mock_dynamodb_cache, reset_cache_singleton) are consumed only by the 4 test files this task deletes, and zero other test file in the directory references any of them. A conftest.py with zero fixtures left serves no purpose, so full deletion is the correct end state - flagging this as a judgment call on the word prune rather than an open blocking question, since the evidence is unambiguous (grep-confirmed zero remaining consumers).
- docs/adr/dependency-injection.md line 155 contains one stale illustrative code snippet referencing IdempotencyService as a Protocol example, which will become inaccurate once this task ships. This file is the legacy, not-yet-archived docs/adr/ tree (TASK-10, still To Do, is the task that reconciles/archives it against decisions/); out of this task's stated scope (app/ only) and out of decisions/reliability.md's blast radius. Not fixed here - flagged for whoever picks up TASK-10, not a blocker for this task's AC/DoD.
- Assumes the full-repo grep already run during planning (repo-wide, excluding .mypy_cache/.pytest_cache build-artifact caches) is authoritative for AC#3/AC#4's zero remaining references bar; re-run as step 11a post-edit as the actual gate, not relying solely on the pre-edit planning grep.

## Blast radius and rollback

- Blast radius: app/infrastructure/idempotency (2 file deletions, 4 small subtractive edits) and its own test suite (4 unit test files plus 1 integration test file deleted, 1 unit conftest.py deleted, test_factory.py pruned). Zero call sites outside this package/its tests reference any deleted symbol (confirmed by repo-wide grep in planning). No terraform/config/API-surface change - purely internal dead-code removal within one infrastructure module.
- Rollback: standard git revert of the single PR; no data migration, no schema/terraform change, no runtime behavior change for any live caller (TASK-5.4.1 already moved every real caller off the deleted stack) - a revert is a no-op from a runtime-behavior perspective, it only restores dead code.
<!-- SECTION:PLAN:END -->
