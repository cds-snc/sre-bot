---
id: TASK-5.4.1
title: >-
  Access Sync: introduce package-owned JobStatusStore; migrate job-status
  polling and lock holder-info off legacy IdempotencyService
status: Done
assignee:
  - '@me'
created_date: '2026-07-27 18:43'
updated_date: '2026-07-27 19:16'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
  - TASK-5.2
references:
  - decisions/reliability.md
  - decisions/layers.md
parent_task_id: TASK-5.4
priority: high
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expand+migrate slice of TASK-5.4. Introduce app/packages/access/sync/job_status_store.py: a concrete JobStatusStore class - mirroring the existing SyncRunRepository (store.py) / AccessRequestRepository conventions in this codebase: no separate Protocol, no vendor-prefixed class name - built on infrastructure.storage.StorageService, reusing the existing sre_bot_idempotency table (hash key idempotency_key, ttl attribute already enabled) - no terraform change. Migrate ALL current get_idempotency_service()/IdempotencyService call sites in app/packages/access/sync off the legacy service onto the new store: job_runner.py (run_user_sync_job, run_platform_sync_job, spawn_user_sync_thread, spawn_platform_sync_thread job-status writes), interactions/http.py (sync_endpoint + get_sync_job_status), interactions/slack.py (handle_sync_user_command, handle_sync_platform_command, handle_sync_status_command), interactions/ingress.py (enqueue_user_sync, enqueue_platform_sync), and platform_lock.py (acquire_lock/current_holder lock-holder-info reporting - added by TASK-5.3, not in TASK-5.4's original Scope paragraph but required for TASK-5.4.2's AC#3 to be reachable). Add get_access_sync_job_status_store() singleton provider to providers.py. End state after this slice + TASK-5.4.2: app/packages/access/sync contains zero AWS/DynamoDB-branded symbol names (class/function/variable names) - only the pre-existing, precedent-consistent prose mentions of the backing store in docstrings/README (same style already used by SyncRunRepository/AccessRequestRepository), plus the required table-name string constant. This slice keeps infrastructure/idempotency/{cache.py,service.py} and DynamoDBCache/IdempotencyService in place (unreferenced but not yet deleted) - deletion is TASK-5.4.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 JobStatusStore concrete class exists in app/packages/access/sync/job_status_store.py, built on infrastructure.storage.StorageService - named and shaped like SyncRunRepository/AccessRequestRepository (no separate Protocol, no vendor-prefixed class name such as DynamoDBJobStatusStore); placement confirmed against packages-python.instructions.md and layers.md Path A guidance
- [x] #2 job_runner.py, interactions/http.py, interactions/slack.py, interactions/ingress.py, and platform_lock.py (including its holder-info reporting) are migrated off get_idempotency_service()/IdempotencyService onto the new JobStatusStore, type-hinted directly as the concrete class (not a Protocol)
- [x] #3 get_access_sync_job_status_store() singleton provider added to packages/access/sync/providers.py, built via get_storage_service()
- [x] #4 grep confirms (a) no remaining get-then-put job-status/holder-info pattern via legacy IdempotencyService anywhere in app/packages/access/sync, and (b) no Dynamo/DynamoDB/boto3 substring appears in any class, function, or variable name in app/packages/access/sync (prose in docstrings/README describing the backing store is acceptable, matching existing SyncRunRepository/AccessRequestRepository style)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass: new job_status_store tests, updated job_runner/ingress/http/slack/platform_lock tests all green
- [x] #2 PR references decisions/reliability.md; notes TASK-5.4.2 as the follow-up contract slice that deletes the now-unreferenced legacy files
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposition context: second-level leaf slice (TASK-5.4 -> TASK-5.4.1/5.4.2 per the implementation-planning skill's single-PR size gate - trigger: TASK-5.4 as originally scoped touches ~13 files across app/packages/access/sync + app/infrastructure/idempotency, exceeding the ~10-file threshold, and is a textbook expand/migrate/contract candidate). This task is the expand+migrate half; TASK-5.4.2 is the contract half (delete legacy files) and depends on this one.

## Grounding (call sites enumerated)

Legacy `get_idempotency_service()`/`IdempotencyService` references in app/packages/access/sync today (repo-wide grep, confirmed 2026-07-27; TASK-5.1/5.2/5.3 all Done):
- interactions/http.py:18 (import), :144-145 (`idempotency = get_idempotency_service()` in `sync_endpoint`, passed into `enqueue_user_sync`/`enqueue_platform_sync`), :~213 (`get_sync_job_status`: `idempotency = get_idempotency_service(); record = idempotency.get(job_id)`).
- interactions/slack.py:17 (import), :~180 (`handle_sync_user_command`), :~276 (`handle_sync_platform_command`), :~357 (`handle_sync_status_command`: `idempotency = get_idempotency_service(); record = idempotency.get(job_id)`).
- interactions/ingress.py:17 (imports `IdempotencyService, IdempotencyStore`), `enqueue_user_sync`/`enqueue_platform_sync` take `idempotency: IdempotencyService` and pass it to `acquire_lock(..., idempotency=idempotency, ...)`, `current_holder(lock_key, idempotency)`, and `spawn_user_sync_thread`/`spawn_platform_sync_thread`.
- job_runner.py:27 (imports `IdempotencyService, IdempotencyStore`); `run_user_sync_job`, `run_platform_sync_job`, `spawn_user_sync_thread`, `spawn_platform_sync_thread` all take `idempotency: IdempotencyService` and call `idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)` for job-status writes only (no `.get()` calls here).
- platform_lock.py:5 (imports `IdempotencyService`); `acquire_lock`/`current_holder` take `idempotency: IdempotencyService` and call `idempotency.set(f"{lock_key}:holder", payload, ttl_seconds=...)` / `idempotency.get(f"{lock_key}:holder")` for best-effort holder-info (added by TASK-5.3; NOT in TASK-5.4's original Scope paragraph but blocks TASK-5.4.2's AC#3 if left unmigrated - confirmed with the human via the decomposition-approval questions).

Existing precedent for the new store's shape (found in codebase, reused directly, confirmed with the human 2026-07-27):
- `packages/access/sync/store.py::SyncRunRepository` and `packages/access/request/store.py::AccessRequestRepository` are the two existing package-level repository precedents. BOTH are plain concrete classes with no separate Protocol layer, and NEITHER has a vendor-prefixed name (not `DynamoDBSyncRunRepository`) even though their docstrings say "DynamoDB-backed repository" in prose. `SyncRunRepository` is even type-hinted directly as the concrete class at its only consumer (`application.py:74`: `repository: SyncRunRepository | None = None`) - there is no repository-level Protocol anywhere in this package today. The swappable seam is `StorageService` itself (infrastructure-level), not a per-repository Protocol - `infrastructure/storage/service.py`'s docstring: "Feature packages MUST NOT call DynamoDBClient or dynamodb_next directly... define a thin repository class that takes StorageService as a constructor argument." `decisions/cloud-portability.md`'s check is "no boto3/botocore imports outside app/integrations/ and app/infrastructure/" - it does not ban descriptive prose about the current backing store, only vendor SDK imports/leakage at the package layer. Conclusion (human-confirmed): `JobStatusStore` must be a single concrete class, same shape as these two precedents - no separate Protocol, no vendor-prefixed name like `DynamoDBJobStatusStore`.
- `terraform/dynamodb.tf:86-103`: `sre_bot_idempotency` table has hash key `idempotency_key` (no range key), TTL attribute `ttl` already enabled. decisions/reliability.md explicitly sanctions sharing this table for the new capability ("even if it happens to share a table with idempotency records"). Reusing it means zero terraform change.
- Legacy `infrastructure/idempotency/dynamodb.py::DynamoDBCache.get/set` serialize the record as a `response_json` JSON string attribute (not nested-dict via TypeSerializer) - deliberately mirrored below to avoid a real behavior-changing risk: boto3's `TypeSerializer`/`TypeDeserializer` round-trips nested ints as `Decimal`, not `int`, if the record dict were stored as a native nested attribute instead of a JSON string. Job records contain int fields (`users_synced`, `orphans_found`, etc. in `CompletedPlatformRecord`) - storing as JSON preserves exact types with zero behavior change.

## Human-approved design decisions

1. **Package-owned, not infra-owned.** Unlike TASK-5.3's lease helper (promoted to `infrastructure/idempotency/lease.py` because TASK-6's cross-cutting scheduler also needs it), nothing outside access-sync needs job-status/holder-info records today - this stays a package-owned class per `.github/instructions/packages-python.instructions.md` and decisions/layers.md's Path-A-vs-Path-B guidance, confirmed with the human.
2. **Built on `infrastructure.storage.StorageService`, not a new DynamoDB access path.** DRY / 12-factor "backing services as attached resources" - reuse the existing generic, swappable storage capability (same as `SyncRunRepository`) instead of hand-rolling a second boto3-facing store; confirmed with the human citing https://12factor.net/backing-services.
3. **Reuse the `sre_bot_idempotency` table**, no terraform change - confirmed with the human.
4. **Migrate `platform_lock.py`'s holder-info too**, even though the original TASK-5.4 Scope paragraph didn't name it - confirmed with the human as required for TASK-5.4.2's AC#3.
5. **`JobStatusStore` is a single concrete class, not a Protocol+implementation pair, and carries no vendor prefix.** Corrected 2026-07-27 after the human asked whether any AWS/DynamoDB terminology would remain in app/packages/access/ after both subtasks: the original plan's `JobStatusStore` Protocol + `DynamoDBJobStatusStore` implementation deviated from this codebase's own precedent (`SyncRunRepository`/`AccessRequestRepository`, both plain concrete classes, no vendor prefix) and needlessly introduced a vendor-branded symbol name into the package layer. Fixed to match precedent exactly - no transitory/inconsistent state is left after this slice.

## Ordered steps

1. **app/packages/access/sync/job_status_store.py (NEW)**: single concrete `JobStatusStore` class (no separate Protocol, mirrors `SyncRunRepository`/`AccessRequestRepository`). Constructor takes `storage: StorageService`. `put(key: str, record: dict[str, Any], ttl_seconds: int) -> None` writes `{"idempotency_key": key, "record_json": json.dumps(record), "ttl": int(time.time()) + ttl_seconds}` via `storage.put(TABLE, item)`. `get(key: str) -> dict[str, Any] | None` calls `storage.get(TABLE, {"idempotency_key": key})`, returns `None` on `is_success=False` (covers not-found) or malformed/missing `record_json`, otherwise `json.loads(record_json)`. `TABLE = "sre_bot_idempotency"`. Module docstring documents the reliability.md rationale (not idempotency dedup; shares the table deliberately; JSON serialization chosen to avoid Decimal round-trip changes) using the same "DynamoDB-backed" prose style as `SyncRunRepository`'s docstring - descriptive prose about the backing store is fine and precedent-consistent; only the class name itself must stay vendor-neutral.
2. **app/packages/access/sync/providers.py**: add `from packages.access.sync.job_status_store import JobStatusStore`; add `get_access_sync_job_status_store() -> JobStatusStore` (`functools.lru_cache(maxsize=1)`) returning `JobStatusStore(storage=get_storage_service())` (mirrors `get_sync_run_repository()`'s exact shape).
3. **app/packages/access/sync/platform_lock.py**: replace `IdempotencyService` import with `JobStatusStore` from `packages.access.sync.job_status_store`; rename `acquire_lock`'s and `current_holder`'s `idempotency: IdempotencyService` parameter to `job_status_store: JobStatusStore`; swap `idempotency.set(...)` -> `job_status_store.put(...)` and `idempotency.get(...)` -> `job_status_store.get(...)`.
4. **app/packages/access/sync/interactions/ingress.py**: replace `IdempotencyService` import; rename `enqueue_user_sync`/`enqueue_platform_sync`'s `idempotency` parameter to `job_status_store: JobStatusStore`; update the `acquire_lock(..., job_status_store=job_status_store, ...)` and `current_holder(lock_key, job_status_store)` call sites; update the `spawn_user_sync_thread`/`spawn_platform_sync_thread` calls to pass `job_status_store=job_status_store`.
5. **app/packages/access/sync/job_runner.py**: replace `IdempotencyService` import with `JobStatusStore`; rename the `idempotency` parameter to `job_status_store` in `run_user_sync_job`, `run_platform_sync_job`, `spawn_user_sync_thread`, `spawn_platform_sync_thread`; swap all `idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)` -> `job_status_store.put(job_id, payload, ttl_seconds=job_ttl_seconds)`.
6. **app/packages/access/sync/interactions/http.py**: replace `from infrastructure.idempotency import get_idempotency_service` with `get_access_sync_job_status_store` added to the existing `packages.access.sync.providers` import; in `sync_endpoint`, `job_status_store = get_access_sync_job_status_store()` passed as `job_status_store=` into `enqueue_user_sync`/`enqueue_platform_sync`; in `get_sync_job_status`, `job_status_store = get_access_sync_job_status_store(); record = job_status_store.get(job_id)`.
7. **app/packages/access/sync/interactions/slack.py**: same import swap; update all three handlers (`handle_sync_user_command`, `handle_sync_platform_command`, `handle_sync_status_command`) to construct/use `job_status_store` instead of `idempotency`.
8. **Final verification (part of AC#4, run before marking done)**: `grep -rniE "dynamo|boto3" app/packages/access/sync --include=*.py | grep -viE "docstring|^.*#.*dynamo"` reviewed by hand to confirm any remaining hits are only prose in docstrings/comments (consistent with `SyncRunRepository`/`AccessRequestRepository` style), never a class/function/variable identifier. Expected zero identifier-level hits.

## AC traceability

- AC#1 (concrete class, precedent-consistent naming) <- step 1; test: `test_job_status_store.py` (direct unit tests against the concrete `JobStatusStore` class - no protocol-satisfaction test needed, matching how `SyncRunRepository` is tested).
- AC#2 (all 5 call sites migrated) <- steps 3-7; tests: updated `test_job_runner.py`, `test_platform_lock.py`, `test_access_sync_routes.py` (all pass with renamed `job_status_store` fixtures/kwargs and no reference to `get_idempotency_service`), plus new `test_access_sync_slack_status.py`.
- AC#3 (provider added) <- step 2; test: `test_providers.py::test_get_access_sync_job_status_store_returns_singleton`.
- AC#4 (grep clean, both legacy-call and vendor-naming) <- steps 3-7 collectively plus step 8; verified via `grep -rn "get_idempotency_service\|IdempotencyService" app/packages/access/sync` returning empty, and the step-8 vendor-naming review; both run as manual verification steps before marking AC#4, not pytest assertions.

## Test matrix

New file `app/tests/unit/packages/access/sync/test_job_status_store.py`:
- `test_put_serializes_record_as_json_with_ttl` - mock `StorageService.put`, assert item has `idempotency_key`, `record_json` (valid JSON matching input dict), `ttl` ~= now + ttl_seconds.
- `test_get_returns_deserialized_record` - mock `StorageService.get` success with `record_json`.
- `test_get_returns_none_when_not_found` - mock `StorageService.get` returning `is_success=False` (NOT_FOUND).
- `test_get_returns_none_when_record_json_missing_or_malformed` - defensive path (boundary).

Updated files (mechanical rename, no behavior change - verify with existing assertions unchanged apart from names):
- `test_job_runner.py`: rename `idempotency` MagicMock/kwarg to `job_status_store` in all ~12 call sites; assertions `idempotency.set.call_count`/`call_args_list` -> `job_status_store.put...`.
- `test_platform_lock.py`: rename `idempotency=idempotency` kwargs to `job_status_store=job_status_store`; `idempotency.set.assert_called_once_with(...)` -> `job_status_store.put.assert_called_once_with(...)`; `current_holder(key, idempotency)` -> `current_holder(key, job_status_store)`.
- `test_access_sync_routes.py`: patch target `packages.access.sync.interactions.http.get_idempotency_service` -> `packages.access.sync.interactions.http.get_access_sync_job_status_store`; rename `fake_idempotency` -> `fake_job_status_store` (still a MagicMock with `.get.return_value`).
- `test_providers.py`: add a case for the new provider's singleton behavior.

New file `app/tests/unit/packages/access/sync/test_access_sync_slack_status.py` (no direct slack-handler tests exist today - this is new coverage required by AC#2 naming slack.py as a migration target):
- `test_handle_sync_status_command_returns_status_message_when_job_found` - patch `get_access_sync_job_status_store` to return a store whose `.get()` yields a completed-record dict; assert the formatted `CommandResponse` message.
- `test_handle_sync_status_command_returns_not_found_message_when_job_missing` - store `.get()` returns `None`; assert the not-found message/ephemeral flag.

## Assumptions and doubts

- Assumes `StorageService.get`'s `NOT_FOUND` `OperationResult` (`is_success=False`) is the only "miss" signal the new store needs to distinguish from a real error for logging purposes; verified by reading `infrastructure/storage/service.py::DynamoDBStorageService.get` (returns `OperationResult.error(OperationStatus.NOT_FOUND, ...)` on missing item). `get()` will not log at error level for this expected case (mirrors legacy `DynamoDBCache.get`'s debug-level miss logging).
- Assumes no other package currently or imminently needs a generic job-status-shaped store (checked: TASK-6's Tier-2 lease is a different capability, already served by `infrastructure/idempotency/lease.py`). If that assumption changes, promote `job_status_store.py` to `infrastructure/` in a follow-up, mirroring TASK-5.3's precedent - do not preemptively over-generalize now.
- Assumes storing `record_json` as a JSON string (not a native nested DynamoDB map via `StorageService`'s `TypeSerializer`) is acceptable even though `SyncRunRepository` stores fields as native top-level attributes; this is a deliberate deviation to avoid the Decimal-coercion risk documented above, not an oversight - flagged explicitly in the module docstring for future readers.
- Assumes existing lock-holder `:holder` keys and bare `job_id` keys (no prefix) can be reused unchanged (no re-keying/migration) - in-flight held locks or job records at deploy time will simply stop being found by `.get()` for old-format keys only if the key string itself changes, which it does not; only the writer class changes. No data migration needed.

## Blast radius and rollback

- Scope confined to `app/packages/access/sync/**` (one package) plus a new provider dependency on the already-shared `infrastructure/storage` service; `infrastructure/idempotency/**` is untouched in this slice (TASK-5.4.2 handles deletion), so any problem here cannot break other TASK-5.x consumers of `IdempotencyStore`/lease.
- A single `git revert` of this PR fully restores prior behavior: legacy `cache.py`/`service.py`/`get_idempotency_service()` remain in place and unmodified in this slice, so reverting simply un-migrates the five call sites back onto them - no ordering constraint, no manifest/env var changes.
- Runtime risk: if `JobStatusStore` has a bug, blast radius is limited to job-status polling (GET /sync-runs/{job_id}, Slack status command returning "not found" instead of real status) and lock holder-info display (Slack "already running" message losing the existing job_id detail) - the actual lock correctness (claim/release, TASK-5.3) is unaffected since it uses the separate `IdempotencyStore`/lease primitive, not this store.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented package-owned JobStatusStore in app/packages/access/sync/job_status_store.py on top of infrastructure.storage.StorageService (shared sre_bot_idempotency table, JSON record serialization, TTL writes).\n\nMigrated all access-sync job-status and holder-info call paths off legacy IdempotencyService to JobStatusStore: app/packages/access/sync/job_runner.py, app/packages/access/sync/interactions/ingress.py, app/packages/access/sync/interactions/http.py, app/packages/access/sync/interactions/slack.py, and app/packages/access/sync/platform_lock.py. Added singleton provider get_access_sync_job_status_store() in app/packages/access/sync/providers.py.\n\nAlso aligned prose in app/packages/access/sync/job_models.py to reference JobStatusStore.\n\nTest evidence:\n- cd /workspace/app && uv run pytest tests/unit/packages/access/sync/test_job_status_store.py tests/unit/packages/access/sync/test_access_sync_slack_status.py tests/unit/packages/access/sync/test_job_runner.py tests/unit/packages/access/sync/test_platform_lock.py tests/unit/packages/access/sync/test_access_sync_routes.py tests/unit/packages/access/sync/test_providers.py  -> 34 passed\n- cd /workspace/app && uv run ruff check .  -> passed\n- cd /workspace/app && uv run pytest tests --ignore=tests/smoke -q  -> 2950 passed, 37 skipped\n- cd /workspace/app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'  -> fails in pre-existing unrelated modules (integrations/aws, modules/incident, packages/geolocate, infrastructure/resilience)\n- grep checks:\n  * grep -Rni --include='*.py' -E 'get_idempotency_service|IdempotencyService' packages/access/sync  -> no matches\n  * grep -Rni --include='*.py' -E 'dynamo|dynamodb|boto3' packages/access/sync  -> matches only prose/docstrings (no class/function/variable names)\n\nDoD items left for human verification:\n- Ensure PR description references decisions/reliability.md.\n- Ensure PR notes call out TASK-5.4.2 as follow-up contract slice deleting now-unreferenced legacy idempotency files.
<!-- SECTION:NOTES:END -->
