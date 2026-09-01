---
id: TASK-25.3
title: >-
  Unify MaxMind client onto one factory + classify_maxmind_error; migrate legacy
  tuple consumers
status: To Do
assignee: []
created_date: '2026-08-05 16:13'
updated_date: '2026-09-01 14:17'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.5
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/maxmind/client.py
  - app/api/v1/routes/geolocate.py
  - app/jobs/scheduled_tasks.py
parent_task_id: TASK-25
priority: high
ordinal: 122000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/maxmind exports exactly one client construction path + classify_maxmind_error(exc) -> (OperationStatus, error_code, retry_after) mapping AddressNotFoundError/ValueError/GeoIP2Error; the legacy module-level geolocate(ip)->tuple|str and healthcheck()->bool functions are deleted
- [ ] #2 api/v1/routes/geolocate.py and jobs/scheduled_tasks.py (the two legacy tuple/bool consumers) are migrated to call the classify boundary and consume OperationResult, not tuple|str/bool
- [ ] #3 packages/geolocate's existing OperationResult-based path (adapters/maxmind.py, service.py) is unchanged/behavior-neutral
- [ ] #4 classify_maxmind_error has unit test coverage: each mapped exception family -> expected status/error_code/retry_after; one unmapped exception propagates
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
CONTEXT (verified 2026-09-01)
- Dep TASK-22.5: Done. Dep TASK-23/TASK-23.3: CLI still shows To Do, but human confirmed
  2026-09-01 both are approved and only pending merge - will land before implementation on
  this task starts. Not an actual blocker (23.3's AWS/Google `_next` dispatcher convergence
  has zero technical overlap with MaxMind regardless). Not set to Done here - only humans
  move tasks to the terminal status after verifying Definition of Done.
- `integrations/maxmind/client.py` today (shipped by TASK-22.1) already has TWO layers:
  `MaxMindClient.geolocate()`/`.healthcheck()` (return `OperationResult`, classification
  inlined in the method's own except blocks) coexisting with legacy module-level
  `geolocate(ip)->tuple|str` / `healthcheck()->bool` (used only by the 2 legacy consumers
  named in this task's refs). `packages/geolocate/service.py` + `adapters/maxmind.py`
  already consume the `OperationResult` path exclusively (AC#3 requires this untouched).
- Real call sites of the legacy functions (grep-confirmed, no others repo-wide):
  `app/api/v1/routes/geolocate.py:4,13` (`from integrations import maxmind`;
  `maxmind.geolocate(ip)`), `app/jobs/scheduled_tasks.py:12,126`
  (`from integrations import maxmind`; `"maxmind": maxmind.healthcheck` inside
  `integration_healthchecks()`'s `dict[str, Callable[[], bool]]`, alongside
  google_drive/opsgenie/identity_store bool-healthchecks - untouched siblings).
- Module-level `MAXMIND_DB_PATH = get_maxmind_settings().MAXMIND_DB_PATH` (client.py:18) is
  used only by the legacy `geolocate()`/`healthcheck()` pair - safe to delete with them.
- `decisions/errors-and-http.md`'s `operation_result_to_response()` helper (TASK-28,
  middleware/edge trio) does not exist yet - existing routes are explicitly tolerated to keep
  bare `HTTPException` until then; this task maps `OperationResult` status to HTTPException
  status codes inline (NOT_FOUND->404, PERMANENT_ERROR->400, TRANSIENT_ERROR->503), per the
  decision's own status table, rather than waiting on TASK-28.
- ARCHITECTURE TENSION FLAGGED (not silently resolved): outbound-clients.md's ideal shape is
  "clients raise, adapters classify" - a maximally pure implementation would make
  `MaxMindClient` raise and move classification into `packages/geolocate/adapters/maxmind.py`.
  This task's own AC#3 blocks that (pins `adapters/maxmind.py`/`service.py` unchanged, which
  depend on `MaxMindClient.geolocate()` already returning a classified `OperationResult`).
  Resolution: keep `MaxMindClient.geolocate()`'s public OperationResult-returning contract
  exactly as-is (zero behavior change), but refactor its internals to call the new
  `classify_maxmind_error()` for the 3 named exception families instead of hardcoding
  status/error_code inline (DRY, testable per AC#4), while its own untouched except clauses
  for `OSError`/`FileNotFoundError`/generic `Exception` (outside AC#1's named 3 families)
  keep their current ad hoc handling unchanged. A follow-up to fully move classification into
  the adapter (making `MaxMindClient` itself raise-only) is optional future work, not this
  task's scope - flagged for human confirmation, not decided unilaterally.

TARGET SHAPE (app/integrations/maxmind/client.py)
1. Add module-level `classify_maxmind_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]`,
   mirroring `integrations/aws/client.py::classify_aws_error`'s signature/shape:
   - `AddressNotFoundError` -> `(OperationStatus.NOT_FOUND, "IP_NOT_FOUND", None)`
   - `ValueError` -> `(OperationStatus.PERMANENT_ERROR, "INVALID_IP_FORMAT", None)`
   - `GeoIP2Error` -> `(OperationStatus.TRANSIENT_ERROR, "GEOIP2_ERROR", None)`
   - anything else -> `raise exc` (unmapped propagates, per AC#4/outbound-clients.md)
2. Refactor `MaxMindClient.geolocate()`'s three matching except blocks to call
   `classify_maxmind_error(e)` for status/error_code (keep each block's own message string
   exactly as today); leave the `OSError`/`FileNotFoundError` and catch-all `Exception`
   except blocks untouched (out of classify_maxmind_error's named scope, preserves AC#3).
3. Delete module-level `geolocate(ip) -> tuple|str`, `healthcheck() -> bool`, and the
   module-level `MAXMIND_DB_PATH` constant (AC#1).
4. `app/integrations/maxmind/__init__.py`: drop `geolocate`/`healthcheck` from the import
   and `__all__`; add `classify_maxmind_error`.

CONSUMER MIGRATIONS (AC#2)
5. `app/api/v1/routes/geolocate.py`: replace `maxmind.geolocate(ip)` tuple/str handling with
   `result = maxmind.get_maxmind_client().geolocate(ip_address=ip)`; branch on
   `result.status` (import `OperationStatus` from `infrastructure.operations`):
   `NOT_FOUND` -> `HTTPException(404, detail=result.message)`; `PERMANENT_ERROR` ->
   `HTTPException(400, detail=result.message)`; `TRANSIENT_ERROR` ->
   `HTTPException(503, detail=result.message)`; else build the response dict from
   `result.data` (same keys as today: country_code/city/latitude/longitude ->
   country/city/latitude/longitude + map_links). Keep `from integrations import maxmind`
   import style (only the called symbol changes).
6. `app/jobs/scheduled_tasks.py::integration_healthchecks()`: replace
   `"maxmind": maxmind.healthcheck` with
   `"maxmind": lambda: maxmind.get_maxmind_client().healthcheck().is_success` - preserves the
   dict's uniform `Callable[[], bool]` contract shared with google_drive/opsgenie/
   identity_store (those 3 are out of scope, untouched).

TEST CHANGES
7. Delete `app/tests/unit/integrations/maxmind/test_maxmind_client.py` wholesale (every test
   in it exercises the now-deleted module-level `geolocate`/`healthcheck` functions).
8. `app/tests/unit/integrations/maxmind/test_operation_client.py`: add a test class for
   `classify_maxmind_error` (AC#4) - one test per mapped family (AddressNotFoundError/
   ValueError/GeoIP2Error) asserting the exact `(status, error_code, retry_after)` tuple, plus
   one test passing an unmapped exception (e.g. `RuntimeError`) and asserting it propagates
   (`pytest.raises`). Existing `MaxMindClient.geolocate()`/`.healthcheck()` tests in this file
   need zero assertion changes (behavior-neutral refactor).
9. `app/tests/api/v1/test_geolocate.py`: rewrite both tests to patch
   `api.v1.routes.geolocate.maxmind.get_maxmind_client` (returning a `Mock` whose
   `.geolocate.return_value` is an `OperationResult`), asserting 200 success body unchanged,
   and split the old single "failure" test into two: NOT_FOUND -> 404, PERMANENT_ERROR (bad
   IP format) -> 400 (status code changes from the old code's blanket 404 - flagged below).
10. `app/tests/integration/jobs/test_scheduled_tasks_integration.py`: update
    `test_healthcheck_all_healthy`/`test_healthcheck_partial_failures` to set
    `mock_maxmind.get_maxmind_client.return_value.healthcheck.return_value =
    OperationResult.success(...)` / a non-success `OperationResult`, instead of setting
    `mock_maxmind.healthcheck.return_value` directly.

AC-TO-STEP-TO-TEST TRACEABILITY
- AC#1 (one construction path + classify_maxmind_error; legacy tuple/bool fns deleted) ->
  Steps 1-4 -> tests: step 8's new classify tests + step 7's deletion (their absence proves
  the legacy functions are gone; `grep -rn "def geolocate(ip)\|def healthcheck()"
  app/integrations/maxmind/client.py` returns nothing).
- AC#2 (both legacy consumers migrated to classify boundary + OperationResult) -> Steps 5-6
  -> tests: step 9 (route) + step 10 (job healthcheck).
- AC#3 (packages/geolocate path unchanged/behavior-neutral) -> verified by NOT touching
  `app/packages/geolocate/adapters/maxmind.py` / `app/packages/geolocate/service.py` at all,
  and by step 8's requirement that existing `MaxMindClient.geolocate()`/`.healthcheck()` tests
  need zero assertion changes -> tests: existing `app/tests/unit/packages/geolocate/
  test_service.py` and `test_service_import_boundaries.py` run unmodified and stay green.
- AC#4 (classify_maxmind_error unit coverage) -> Step 1 -> tests: step 8.

TEST MATRIX
| Scenario | Exception | Expected classify_maxmind_error tuple | Expected route HTTP | Expected job healthcheck bool |
|---|---|---|---|---|
| Not found | AddressNotFoundError | (NOT_FOUND, "IP_NOT_FOUND", None) | 404 | n/a |
| Invalid IP | ValueError | (PERMANENT_ERROR, "INVALID_IP_FORMAT", None) | 400 | n/a |
| GeoIP2 DB error | GeoIP2Error | (TRANSIENT_ERROR, "GEOIP2_ERROR", None) | 503 | n/a |
| Unmapped | e.g. RuntimeError | propagates (raises) | n/a (not reachable via classify_maxmind_error from geolocate() since its own except Exception still catches it, per AC#3) | n/a |
| Healthcheck success | - | - | n/a | True |
| Healthcheck failure | - | - | n/a | False |

ASSUMPTIONS / DOUBTS FOR HUMAN REVIEW (not silently decided)
1. Route HTTP status for invalid-IP-format changes from the old code's blanket 404 to 400
   (per decisions/errors-and-http.md's PERMANENT_ERROR->400 mapping) - a real, intentional
   behavior change for API callers hitting `/geolocate/{ip}` with a malformed IP. Flagging for
   sign-off rather than silently preserving the old (arguably wrong) 404-for-everything shape.
2. `MaxMindClient` keeps doing its own OperationResult classification internally (not a pure
   raise-only client) because AC#3 pins its two existing consumers' contract - see the
   ARCHITECTURE TENSION note above. Confirm this is acceptable as this task's final shape
   (vs. filing a separate future task to fully relocate classification into the adapter).
3. `jobs/scheduled_tasks.py`'s healthcheck dict stays `Callable[[], bool]`-typed uniformly
   (maxmind's OperationResult collapsed to `.is_success` at the call site) rather than
   redesigning the whole healthcheck registry to carry OperationResult end-to-end - redesigning
   the other 3 vendors' healthcheck shape is out of this task's scope.
4. RESOLVED 2026-09-01: TASK-23/TASK-23.3 dependency status - human confirmed both are
   approved and merging before this task's implementation starts; no longer an open doubt.

BLAST RADIUS / ROLLBACK
- Production files touched: app/integrations/maxmind/client.py, app/integrations/maxmind/__init__.py,
  app/api/v1/routes/geolocate.py, app/jobs/scheduled_tasks.py (4 files, one vendor, no terraform/CI).
- Test files touched: 1 deleted (test_maxmind_client.py), 3 edited (test_operation_client.py,
  test_geolocate.py, test_scheduled_tasks_integration.py).
- No consumers outside these 2 call sites and packages/geolocate (already verified untouched).
- Fully reversible via a single git revert; no data migration, no schema/terraform change,
  no new external dependency.
- SIZE GATE VERDICT: fits comfortably in one PR (~60-80 net production LOC across 4 files,
  one vendor/subsystem, no terraform/CI, no mixed refactor+unrelated-behavior). No decomposition
  needed.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @gcharest
created: 2026-09-01 14:17
---
Correction (human, 2026-09-01): TASK-23/TASK-23.3 are approved and only pending merge, not blocked - will land before implementation starts on this task. Dependency status doubt in the plan resolved accordingly.
---
<!-- COMMENTS:END -->
