---
id: TASK-23.2
title: >-
  Converge the DynamoDB idempotency store onto get_aws_client +
  classify_aws_error
status: To Do
assignee: []
created_date: '2026-08-31 17:35'
updated_date: '2026-08-31 18:51'
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
- [ ] #3 The moto-backed conformance suite under tests/integration/infrastructure/idempotency passes with its conftest importing no symbol from any _next module (neither integrations.aws.client_next nor integrations.aws.dynamodb_next); both its ENVIRONMENT override target and AWS_REGION come from integrations.aws.client
- [ ] #4 Unit tests cover the three claim outcomes, complete, release, and one unmapped SDK exception propagating rather than being swallowed into a permanent error
- [ ] #5 infrastructure/idempotency/factory.py owns DynamoDB client construction: get_idempotency_store() and build_idempotency_store() both obtain the client via get_aws_client for the dynamodb service and inject it into DynamoDBIdempotencyStore, pinned by a unit test on the provider wiring
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 mypy, ruff and pytest (excluding smoke) green from app/
- [ ] #2 Single git revert restores the previous behavior; PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Grounding

Verified against live code this session (not the task prose):

- `app/infrastructure/idempotency/dynamodb.py:15` imports `delete_item, get_item, put_item` from `integrations.aws.dynamodb_next`; 3 call sites: `put_item` in `claim` (~line 50) and `complete` (~line 100), `get_item` in `claim` (~line 76), `delete_item` in `release` (~line 116).
- `app/infrastructure/idempotency/factory.py:23` and `:31` construct `DynamoDBIdempotencyStore(idempotency_settings=...)` with no client.
- Canonical primitive: `app/integrations/aws/client.py:28 get_aws_client` (boto3 `Config(retries={"mode": ...})` + connect/read timeouts + dynamodb-local endpoint gate for ENVIRONMENT in local/dev/ci) and `:91 classify_aws_error` (BotoCoreError -> TRANSIENT; ClientError mapped by code; `ConditionalCheckFailedException` -> PERMANENT_ERROR with code preserved; everything else `raise exc`).
- Shape to follow: `app/infrastructure/storage/service.py` (`DynamoDBStorageService.__init__(dynamodb)`, `_map_sdk_exception`, `except (ClientError, BotoCoreError)`) and its provider `get_storage_service()` at `service.py:302` (`cast(DynamoDBClient, get_aws_client("dynamodb"))`).
- Typed stub: `types-boto3[...,dynamodb,...]` is already a dev dep (`app/pyproject.toml:169`). VERIFIED this session with a scratch mypy run: `types_boto3_dynamodb.client.DynamoDBClient` accepts the raw attribute-format payloads this store uses (`Item={"k": {"S": ...}}`, `ExpressionAttributeValues={":now": {"N": ...}}`, `ConsistentRead=True`, `resp.get("Item")`) with zero errors. So use the stub under `TYPE_CHECKING` per decisions/sdk-typing.md item 2 - do NOT hand-roll a local `Protocol` (storage/service.py's `DynamoDBClient` Protocol is a pre-existing deviation, out of scope).
- After this slice, the only remaining `dynamodb_next` consumer is `infrastructure/resilience/retry/dynamodb_store.py` (10 calls) - TASK-23.3. `dynamodb_next.py` is NOT deleted here.

## Steps

1. `app/infrastructure/idempotency/dynamodb.py` - drop the `integrations.aws.dynamodb_next` import; add `from botocore.exceptions import BotoCoreError, ClientError`, `from integrations.aws.client import classify_aws_error`, and `if TYPE_CHECKING: from types_boto3_dynamodb.client import DynamoDBClient`.
2. Same file - change the constructor to inject the client first: `__init__(self, dynamodb: "DynamoDBClient", idempotency_settings: IdempotencySettings, table_name: str = IDEMPOTENCY_TABLE)`, storing `self._dynamodb`. Keep `table_name`, `record_ttl_seconds`, `in_progress_ttl_seconds`, `self.log` exactly as they are (`test_factory.py:52-53` asserts the two TTL attributes).
3. `claim()` - keep the item payload, `ConditionExpression`, `ExpressionAttributeNames`/`Values` byte-identical; only the invocation changes:
   - `try: self._dynamodb.put_item(TableName=self.table_name, Item=..., ConditionExpression=..., ...)` then `return ClaimOutcome(result=ClaimResult.NEW)`.
   - `except (ClientError, BotoCoreError) as exc:` -> `status, error_code, _ = classify_aws_error(exc)` (unmapped exceptions re-raise from inside `classify_aws_error` and propagate untouched); `if error_code != "ConditionalCheckFailedException": raise RuntimeError(f"Failed to claim idempotency key: {exc}") from exc`; otherwise fall through to the read path.
4. `claim()` read path - `response = self._dynamodb.get_item(TableName=self.table_name, Key={PARTITION_KEY: {"S": key}}, ConsistentRead=True)`; `item = response.get("Item")`; if absent -> `ClaimOutcome(result=ClaimResult.IN_PROGRESS)`. Wrap in `try/except (ClientError, BotoCoreError) as exc:` -> `classify_aws_error(exc)` (so unmapped errors still propagate), log the classified status/code at warning, then return `IN_PROGRESS`. This preserves today's "unreadable record is never claimable" safety property (see Doubt D1). Status/outcome decoding (`status == COMPLETED` -> `json.loads(outcome_json)`, missing `outcome_json` -> `outcome=None`) is unchanged.
5. `complete()` / `release()` - wrap the single `put_item` / `delete_item` in `try/except (ClientError, BotoCoreError) as exc:` -> `classify_aws_error(exc)` then `raise RuntimeError(f"Failed to complete idempotency key: {exc}") from exc` / `...release...`. Same message prefixes as today so log/alert greps keep matching.
6. `app/infrastructure/idempotency/factory.py` - add `from typing import TYPE_CHECKING, cast` + `from integrations.aws.client import get_aws_client`; build the client once per construction: `dynamodb = cast("DynamoDBClient", get_aws_client("dynamodb"))` and pass it into both `get_idempotency_store()` (`:23`) and `build_idempotency_store()` (`:31`). No `role_arn` - dynamodb has no `AwsSettings.SERVICE_ROLE_MAP` entry (same-account service; confirmed for TASK-22.2 and unchanged).
7. `app/tests/integration/infrastructure/idempotency/conftest.py` - replace `from integrations.aws import client_next as aws_client_next` and `from integrations.aws.dynamodb_next import AWS_REGION` with `from integrations.aws.client import AWS_REGION, get_aws_client`; `_set_moto_aws_credentials` patches `aws_client.app_settings.ENVIRONMENT = "test"` on `integrations.aws.client` (note: `get_app_settings` is `lru_cache`d, so both modules share one instance - the repoint is about import hygiene ahead of TASK-23.3's deletion, not a semantic change). In both DynamoDB fixtures, build the store's client INSIDE the `moto.mock_aws()` block via `get_aws_client("dynamodb")` and inject it. Zero changes to `test_idempotency_store_conformance.py`.
8. `app/tests/unit/infrastructure/idempotency/test_dynamodb_store.py` - rewrite the doubles: the `store` fixture takes a `MagicMock(spec=["put_item", "get_item", "delete_item"])`; success = plain return values / `{"Item": {...}}` dicts; contention = `side_effect=ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "..."}}, "PutItem")`. Keep every existing assertion (single conditional put, `get_item` not called on NEW, COMPLETED payload round-trip, IN_PROGRESS, complete's `status`/`outcome_json`, release deletes). Change `test_claim_raises_on_unexpected_error_code` to assert the raw `ClientError` propagates (see Risk R1) and add one mapped-but-non-conditional case (e.g. `AccessDeniedException`) still raising `RuntimeError`. Update the module docstring (behavior-only wording; no task IDs/dates).
9. `app/tests/unit/infrastructure/idempotency/test_factory.py` - monkeypatch `infrastructure.idempotency.factory.get_aws_client` with a `MagicMock` in the factory tests so the unit tier builds no real boto3 client; add one test asserting the provider calls `get_aws_client("dynamodb")` once and injects the result (mirrors `tests/unit/infrastructure/storage/test_storage_service.py:316`). Same monkeypatch in `test_lease.py`'s `TestGetLeaseStore` (2 tests, `:86-87`/`:98-99`) which reaches the factory through `get_lease_store` -> `build_idempotency_store`.
10. Validate: `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run ruff check .`, then `make test` (the Makefile's `test-new`/`test-legacy` split - a single whole-tree `pytest` run has 5 known pre-existing cross-directory-pollution failures unrelated to this change).

## AC -> step -> test traceability

- AC#1 (no `dynamodb_next` symbols; holds a boto3 client; try/except + `classify_aws_error`) -> steps 1-6 -> `test_dynamodb_store.py` (all classes) + the new provider-wiring test in `test_factory.py`; grep check: `grep -rn "dynamodb_next" app/infrastructure/idempotency/` returns nothing.
- AC#2 (claim/complete/release outcomes unchanged) -> steps 3-5 -> unchanged `test_idempotency_store_conformance.py` running green against the moto-backed store (the real ConditionExpression semantics, not a fake) + the COMPLETED/IN_PROGRESS unit tests.
- AC#3 (moto conformance suite passes, no `_next` import, ENVIRONMENT override on `integrations.aws.client`) -> step 7 -> `pytest tests/integration/infrastructure/idempotency`.
- AC#4 (three claim outcomes, complete, release, one unmapped SDK exception propagates) -> steps 3-5, 8 -> `test_dynamodb_store.py`.
- AC#5 (factory owns client construction) -> step 6 -> new provider test in `test_factory.py`.

## Test matrix

| Tier | File | Cases |
| --- | --- | --- |
| unit | `tests/unit/infrastructure/idempotency/test_dynamodb_store.py` | NEW (single conditional put, no `get_item`); COMPLETED w/ outcome payload; IN_PROGRESS; complete writes `status`/`outcome_json`/`ttl`; release deletes; mapped non-conditional `ClientError` -> `RuntimeError`; unmapped `ClientError` -> propagates unchanged |
| unit | `tests/unit/infrastructure/idempotency/test_factory.py` | provider calls `get_aws_client("dynamodb")` once and injects it; singleton/reset/TTL-override behavior unchanged |
| unit | `tests/unit/infrastructure/idempotency/test_lease.py` | existing per-TTL singleton tests, now with the factory's client construction patched |
| integration | `tests/integration/infrastructure/idempotency/test_idempotency_store_conformance.py` | unchanged suite, both params (in-memory + moto DynamoDB), incl. expired-claim takeover |

## Assumptions and doubts

- D1 (needs reviewer opinion): today a FAILED conditional-read inside `claim()` is silently downgraded to `IN_PROGRESS` (`dynamodb.py` ~line 82). The plan keeps that downgrade for *classified* errors but lets *unmapped* ones propagate. The stricter alternative - raise on any read failure - would be a real behavior change on a rare path and is deliberately not taken. Confirm the conservative choice.
- D2: `DynamoDBIdempotencyStore.__init__` gains a required first positional `dynamodb` argument. 5 construction sites exist (factory x2, integration conftest x2, unit fixture x1) - all updated in this PR. Confirmed via repo-wide grep that no other production or test code constructs it.
- D3: `classify_aws_error`'s tuple return is partly discarded in `complete`/`release` (called for its propagate-unmapped side effect and error message). Accepted as the sanctioned mechanism from decisions/outbound-clients.md; the classified status is logged rather than silently dropped.
- D4: retry semantics move from `client_next`'s hand-rolled `time.sleep` loop (Throttling/RequestLimitExceeded/ProvisionedThroughputExceeded, 3 attempts) to boto3-native `Config(retries={"mode": ..., "max_attempts": ...})` configured in `get_aws_client`. Equivalent coverage, no hand-rolled loop - exactly what decisions/outbound-clients.md mandates. Not separately tested here (owned by `tests/unit/integrations/aws/test_aws_client.py`).

## Risks, blast radius, rollback

- R1 (the one intentional behavior change): an UNMAPPED SDK error during `claim`/`complete`/`release` now propagates as the raw `botocore` exception instead of being converted into `OperationResult.permanent_error` and then re-raised as `RuntimeError`. Mapped errors still raise `RuntimeError` with the same message prefix. Required by AC#4 and decisions/outbound-clients.md ("unexpected exceptions are not classified - they propagate and crash loudly"). Callers: `packages/access/sync/providers.py`, `jobs/scheduled_tasks.py` via `run_if_leased`, plus `infrastructure/idempotency/lease.py` - none catch `RuntimeError` specifically (verified), so the change surfaces as a louder failure, not a swallowed one.
- Blast radius: idempotency dedup + every Tier-2 scheduler lease and the Access Sync platform lock go through this store. Contention correctness rests on `ConditionalCheckFailedException`, which `classify_aws_error` preserves verbatim - and the moto-backed conformance suite exercises the real conditional-write semantics, so a regression here fails CI rather than production.
- Not touched: `integrations/aws/dynamodb_next.py`, `client_next.py`, `infrastructure/resilience/retry/dynamodb_store.py` (TASK-23.3), `in_memory.py`, `protocol.py`, `settings.py`, `lease.py` production code, terraform, CI workflows. No baseline files under `app/bin/baselines/` are affected (no `app/integrations/` file is added, moved, or deleted in this slice - re-verified).
- Rollback: single `git revert` - 2 production files and 4 test files, no data/schema/config migration (same table, same item shape, same attribute names).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-31 18:51
---
Human sign-off on the two open plan items (2026-08-31): D1 RESOLVED - keep the existing conservative downgrade in claim(), where a classified read failure still yields IN_PROGRESS; letting some errors pass through silently is acceptable for this slice and will be reassessed later, most likely during the TASK-25.2.x AWS-remainder work. R1 RESOLVED - the behavior change is accepted: unmapped SDK exceptions propagate raw instead of becoming RuntimeError, since the lease/dedup concept is expected to be revisited as a whole in a later task. No plan or AC changes needed; implement as written.
---
<!-- COMMENTS:END -->
