---
id: TASK-23.3
title: Converge the DynamoDB retry store; delete the AWS _next dispatcher generation
status: Done
assignee:
  - '@me'
created_date: '2026-08-31 17:35'
updated_date: '2026-09-01 13:47'
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
- [x] #1 infrastructure/resilience/retry/dynamodb_store.py imports no symbol from integrations.aws.dynamodb_next; all 10 call sites use a boto3 DynamoDB client from integrations.aws.client.get_aws_client wrapped in try/except with classify_aws_error
- [x] #2 claim_record still returns False (not an exception) when the conditional write fails with ConditionalCheckFailedException, and still returns False and logs an error for any other classified failure
- [x] #3 fetch_due, get_stats and get_dlq_entries are covered by tests whose fakes return the real boto3 response shape (a dict with Items / Count), proving the previously list-shaped paginated result no longer breaks them
- [x] #4 find app/integrations -name '*_next.py' returns zero files; integrations/aws/dynamodb_next.py, client_next.py and identity_store_next.py and their tests are deleted, and the _next-generation execute_aws_api_call no longer exists (the separate non-_next execute_aws_api_call in integrations/aws/client.py stays - TASK-25.2 scope)
- [x] #5 The ENVIRONMENT-gated dynamodb-local endpoint matrix test still covers the surviving construction path: its client_next case is repointed to integrations.aws.client.get_aws_client rather than deleted
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 mypy, ruff and pytest (excluding smoke) green from app/
- [x] #2 Single git revert restores the previous behavior; PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Grounding (fresh greps, 2026-08-31)

Remaining `_next` references repo-wide (excluding caches/coverage HTML/backlog), all under `app/`:

- prod: `infrastructure/resilience/retry/dynamodb_store.py` (10 call sites, below); `infrastructure/audit/service.py:4` (docstring mention only)
- modules to delete: `integrations/aws/dynamodb_next.py`, `integrations/aws/client_next.py`, `integrations/aws/identity_store_next.py`
- tests to delete: `tests/unit/integrations/aws/test_dynamodb_next.py`, `tests/integrations/aws/test_client_next.py`, `tests/integrations/aws/test_identity_store_next.py`, `tests/integrations/aws/fixtures_identity_store.py` (grep-verified: its only importer is `test_identity_store_next.py:8`)
- tests to repoint/rewrite: `tests/unit/integrations/aws/test_dynamodb_local_endpoint.py:57-88`, `tests/unit/infrastructure/resilience/retry/{conftest.py,test_dynamodb_store.py,test_resilience_factory.py}`
- guardrail: `bin/baselines/sdk_typing_antipatterns.txt` lines for `integrations/aws/client_next.py`, `dynamodb_next.py`, `identity_store_next.py` (checker `bin/check_sdk_typing.py`, `make` target line 101; stale entries only print INFO, but the baseline is meant to ratchet down)

The 10 `dynamodb_store.py` call sites: put_item `:124` (save); query `:159` (fetch_due), `:416` + `:429` (get_stats), `:467` (get_dlq_entries); update_item `:219` (claim_record), `:309` (mark_permanent_failure), `:386` (increment_attempt); delete_item `:263` (mark_success); get_item `:340` (increment_attempt).

Bug confirmed at source (`client_next.py:214-229` `_paginate_all_results` returns `list[dict]`, `:348` `should_paginate` is True whenever `force_paginate=True`, `dynamodb_next.query` always passes `keys=["Items"], force_paginate=True`):

- `fetch_due` `:172` and `get_dlq_entries` `:475` do `result.data.get("Items", [])` on a LIST -> `AttributeError` whenever any record matches (empty list is falsy, so the empty case silently works today).
- `get_stats` `:424`/`:437` do `result.data.get("Count", 0)`, but with `Select="COUNT"` the pages carry no `Items` key, so `results` stays `[]` -> falsy -> **`get_stats` always returns 0/0/0 today**.

Blast-radius fact found while grounding (new, not in the task text): `infrastructure/resilience/` has **zero production importers** — `grep -rn "infrastructure.resilience" api infrastructure jobs modules packages server main.py` (excluding the package itself) returns nothing, `get_resilience_service()`/`RetryWorker` are never called outside the package, and `RetrySettings.backend` defaults to `"memory"` with `RETRY_BACKEND` set nowhere in terraform/CI/env. `get_stats`/`get_dlq_entries` have no callers at all; `fetch_due`/`claim_record` are called only by `retry/worker.py:113,141`, itself never instantiated in production. So this slice carries no live-traffic risk and the "broken today" paths are currently unreachable — the fix is correctness debt repayment, proven at the unit tier (AC#3), not an incident fix.

## Steps

1. `infrastructure/resilience/retry/dynamodb_store.py` — imports: drop `from integrations.aws import dynamodb_next`; add `from botocore.exceptions import BotoCoreError, ClientError`, `from integrations.aws.client import classify_aws_error`, and `if TYPE_CHECKING: from types_boto3_dynamodb.client import DynamoDBClient`. Mirrors the shipped `infrastructure/idempotency/dynamodb.py` shape exactly.
2. Same file — constructor gains an injected client as first positional arg: `__init__(self, dynamodb: "DynamoDBClient", config: RetryConfig, table_name: str, ttl_days: int = 30)`, storing `self._dynamodb`. Everything else (`config`, `table_name`, `ttl_days`, `_record_counter`, `self.log`, the `dynamodb_retry_store_initialized` log) unchanged.
3. `save()` `:124` — `self._dynamodb.put_item(TableName=self.table_name, Item=dynamodb_item)` in `try`; `except (ClientError, BotoCoreError) as exc:` -> `status, error_code, _ = classify_aws_error(exc)`, log `dynamodb_save_failed` with `record_id`/`error`/`error_code`, then `raise RuntimeError(f"Failed to save retry record: {exc}") from exc`. Success path keeps the `retry_record_saved` debug log and `return record.id`. Item construction is byte-identical.
4. `fetch_due()` `:159` — `response = self._dynamodb.query(TableName=self.table_name, IndexName="status-next_retry_at-index", KeyConditionExpression=..., ExpressionAttributeNames=..., ExpressionAttributeValues=..., Limit=limit * 2)`; `items = response.get("Items", [])`. On `except (ClientError, BotoCoreError)` -> classify, log `dynamodb_fetch_due_failed`, `return []` (same as today). No paginator here: the call is explicitly `Limit`-bounded, so paginating would contradict the limit. Claim filtering / `_item_to_record` / debug log unchanged.
5. `claim_record()` `:219` — `self._dynamodb.update_item(...)` with the same `Key`/`UpdateExpression`/`ConditionExpression`/`ExpressionAttributeValues`; success -> debug log + `return True`. `except (ClientError, BotoCoreError) as exc:` -> `_, error_code, _ = classify_aws_error(exc)`; if `error_code == "ConditionalCheckFailedException"` -> `retry_claim_failed_already_claimed` debug + `return False`; else `dynamodb_claim_failed` error log + `return False` (AC#2). Unmapped exceptions propagate out of `classify_aws_error` (see R1).
6. `mark_success()` `:263` and `mark_permanent_failure()` `:309` — same try/except shape as step 3: classify, log the existing `dynamodb_mark_success_failed` / `dynamodb_mark_permanent_failure_failed` events, re-raise `RuntimeError` with today's message prefixes (`Failed to mark success: ` / `Failed to mark permanent failure: `). Expression building unchanged.
7. `increment_attempt()` `:340` (read) — `response = self._dynamodb.get_item(TableName=..., Key={"record_id": {"S": record_id}})` in `try`; `item = response.get("Item")`; `if item is None:` keep the `retry_record_not_found_for_increment` warning + `return`. `except (ClientError, BotoCoreError)` -> classify, same warning event with the classified `error_code`, `return` (no raise — preserves today's non-fatal read behavior).
8. `increment_attempt()` `:386` (write) — as step 6, keeping the `dynamodb_increment_attempt_failed` log and `RuntimeError(f"Failed to increment attempt: ...")`. Max-attempts -> `mark_permanent_failure` delegation and backoff math untouched.
9. `get_stats()` `:416`/`:429` — **paginated** count per status (decision D1, human-approved): `paginator = self._dynamodb.get_paginator("query")`, then `count = sum(page.get("Count", 0) for page in paginator.paginate(TableName=..., IndexName="status-next_retry_at-index", KeyConditionExpression="#status = :status", ExpressionAttributeNames=..., ExpressionAttributeValues={":status": {"S": "ACTIVE"}}, Select="COUNT"))`, and the same for `"DLQ"`. This restores the aggregate-across-pages intent the old code expressed but never achieved. Extract a small private helper (e.g. `_count_by_status(status: str) -> int | None`, returning `None` on classified failure) so the two blocks are not duplicated; each wrapped in `try/except (ClientError, BotoCoreError)` -> classify + `dynamodb_get_stats_failed` log + count `0`. `claimed_records` stays hardcoded `0`. Same paginator precedent as `infrastructure/storage/service.py::query()`.
10. `get_dlq_entries()` `:467` — like step 4: direct `query(..., Limit=limit)`, `response.get("Items", [])`, classified failure -> `dynamodb_get_dlq_entries_failed` + `return []`. No paginator (the call is `Limit`-bounded).
11. `infrastructure/resilience/retry/factory.py` — add `from typing import cast` + `from integrations.aws.client import get_aws_client`; in the `dynamodb` branch build the client once: `dynamodb = cast("DynamoDBClient", get_aws_client("dynamodb"))` (import the type under the existing `TYPE_CHECKING` block) and pass it into `DynamoDBRetryStore(...)`. No `role_arn` — `dynamodb` has no `AwsSettings.SERVICE_ROLE_MAP` entry (same-account service; re-confirmed). Mirrors `infrastructure/idempotency/factory.py`.
12. `infrastructure/audit/service.py:4` — docstring says "no direct boto3 or dynamodb_next calls"; reword to reference `StorageService` only (the named module ceases to exist). Docstring-only, no behavior. In scope for this PR (human-confirmed).
13. Delete `integrations/aws/dynamodb_next.py`, `integrations/aws/client_next.py`, `integrations/aws/identity_store_next.py` (AC#4). The non-`_next` `execute_aws_api_call` in `integrations/aws/client.py` is explicitly NOT touched (TASK-25.2 scope).
14. Delete `tests/unit/integrations/aws/test_dynamodb_next.py`, `tests/integrations/aws/test_client_next.py`, `tests/integrations/aws/test_identity_store_next.py`, `tests/integrations/aws/fixtures_identity_store.py`. (Side effect: this removes 2 of the 5 known whole-tree cross-directory-pollution failures, which live in `tests/integrations/aws/test_client_next.py`.)
15. `bin/baselines/sdk_typing_antipatterns.txt` — remove the three `_next` lines. Keep the header comments and every other entry. In scope for this PR (human-confirmed).
16. `tests/unit/integrations/aws/test_dynamodb_local_endpoint.py` — repoint the middle parametrized test (AC#5): rename to `test_integrations_aws_client_dynamodb_endpoint_matrix`, import `from integrations.aws import client as aws_client`, monkeypatch `aws_client.boto3` (FakeBoto3/FakeSession capturing `client_config`), `aws_client.app_settings` -> `SimpleNamespace(ENVIRONMENT=environment)` and `aws_client.settings` -> `SimpleNamespace(AWS_REGION="ca-central-1")` (the factory reads the rest via `getattr` defaults), keeping all five environment params and the `endpoint_url` assertion. Reuse the fake-session shape already used in `tests/unit/integrations/aws/test_aws_client.py:26-56`. The other two tests in the file (legacy `integrations.aws.dynamodb`, `modules.aws.aws_access_requests`) are untouched.
17. `tests/unit/infrastructure/resilience/retry/conftest.py` — replace `mock_dynamodb_next` with `mock_dynamodb_client` (`MagicMock(spec=["put_item", "get_item", "delete_item", "update_item", "query", "get_paginator"])`) whose defaults are real boto3 response shapes: `put_item/update_item/delete_item -> {}`, `get_item -> {"Item": {}}`, `query -> {"Items": [], "Count": 0}`, and `get_paginator("query").paginate(...) -> iter([{"Count": 0}])` (a `MagicMock` whose `paginate` returns a list of page dicts, so tests can set multi-page counts). `dynamodb_retry_store` injects the client into the constructor instead of monkeypatching a module, and keeps attaching it for test access (rename `_mock_dynamodb_next` -> `_mock_dynamodb`). Drop the now-unused `OperationResult` import.
18. `tests/unit/infrastructure/resilience/retry/test_dynamodb_store.py` — mechanical rewrite of the doubles only: success cases return plain dicts; failure cases use `side_effect=ClientError({"Error": {"Code": ...}}, "UpdateItem")`. Every existing assertion is preserved, with `table_name=` kwargs becoming `TableName=`. Add the AC#3 cases: `fetch_due` and `get_dlq_entries` with a non-empty `{"Items": [...]}` response (the shape that used to blow up), and `get_stats` driven by paginator pages — including a **multi-page** case (e.g. `[{"Count": 3}, {"Count": 2}]` -> 5) that proves counts aggregate across pages, plus a `Select="COUNT"` kwarg assertion. Add `claim_record` non-conditional mapped failure (e.g. `AccessDeniedException`) -> `False` + error log, and one unmapped-code case asserting the raw `ClientError` propagates (R1). Update the module docstring (behavior-only wording, no module names that will no longer exist).
19. `tests/unit/infrastructure/resilience/retry/test_resilience_factory.py` — replace the three `monkeypatch.setattr("...dynamodb_store.dynamodb_next", ...)` calls (`:41`, `:68`, `:103`) with `monkeypatch.setattr("infrastructure.resilience.retry.factory.get_aws_client", lambda *a, **k: MagicMock())` so the unit tier builds no real boto3 client, and add one test asserting the factory calls `get_aws_client("dynamodb")` once and injects the result into the store (precedent: `tests/unit/infrastructure/storage/test_storage_service.py:316`).
20. Validate: `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` (whole-tree mypy has a ~107-error pre-existing baseline — verify instead that zero errors mention the touched files), `uv run ruff check .`, `make test` (the `test-new`/`test-legacy` split, not a single whole-tree pytest run), `uv run python bin/check_sdk_typing.py`, and the AC#4 check `find app/integrations -name '*_next.py'`.

## AC -> step -> test traceability

- AC#1 (no `dynamodb_next` symbols; all 10 sites on a `get_aws_client` boto3 client + try/except + `classify_aws_error`) -> steps 1-11 -> `tests/unit/infrastructure/resilience/retry/test_dynamodb_store.py` (all classes) + the new factory-wiring test; grep check `grep -rn "dynamodb_next" app/infrastructure/` returns nothing.
- AC#2 (`claim_record` returns False on `ConditionalCheckFailedException`, and False + error log on any other classified failure) -> step 5 -> `TestDynamoDBRetryStoreClaimRecord`: conditional-failure case, mapped non-conditional (`AccessDeniedException`) case, plus the unmapped-propagates case.
- AC#3 (real-shape fakes for `fetch_due`/`get_stats`/`get_dlq_entries`) -> steps 4, 9, 10, 17, 18 -> the non-empty `{"Items": [...]}` cases and the multi-page `{"Count": n}` paginator case in `test_dynamodb_store.py`.
- AC#4 (zero `*_next.py`; three modules + their tests deleted; `_next` `execute_aws_api_call` gone) -> steps 13-15 -> `find app/integrations -name '*_next.py'` empty + `make test` green after deletion + `bin/check_sdk_typing.py` OK.
- AC#5 (endpoint matrix repointed, not deleted) -> step 16 -> `tests/unit/integrations/aws/test_dynamodb_local_endpoint.py::test_integrations_aws_client_dynamodb_endpoint_matrix` (5 params).

## Test matrix

| Tier | File | Cases |
| --- | --- | --- |
| unit | `tests/unit/infrastructure/resilience/retry/test_dynamodb_store.py` | save assigns id / calls `put_item` / sets timestamps; save failure -> `RuntimeError`; `fetch_due` queries the GSI, respects `Limit`, returns records from a non-empty `{"Items": [...]}`, filters unexpired claims, returns `[]` on classified failure; `claim_record` success, conditional-failure -> False, mapped non-conditional -> False + error log, unmapped -> raises; `mark_success` deletes; `mark_permanent_failure` sets DLQ + removes claim; `increment_attempt` reads, releases claim, moves to DLQ at max, no-op on missing item and on classified read failure; `get_stats` sums `Count` across multiple paginator pages, passes `Select="COUNT"`, and returns 0/0/0 on classified failure; `get_dlq_entries` maps a non-empty `{"Items": [...]}` and returns `[]` on failure |
| unit | `tests/unit/infrastructure/resilience/retry/test_resilience_factory.py` | memory/dynamodb/backend-override/unknown-backend behavior unchanged; new: factory calls `get_aws_client("dynamodb")` once and injects it |
| unit | `tests/unit/integrations/aws/test_dynamodb_local_endpoint.py` | 5-environment matrix against `integrations.aws.client.get_aws_client` |

No integration/moto tier is added: there is no existing moto conformance suite for the retry store, and adding one would mix a new capability into a convergence slice (candidate follow-up, mirroring the idempotency conformance suite).

## Assumptions and doubts

- D1 (RESOLVED, human-approved 2026-08-31): `get_stats` uses the `get_paginator("query")` variant and sums `page["Count"]` across pages, rather than a single page-scoped `query(Select="COUNT")`. This restores the aggregate intent the old code expressed but never achieved (it silently returned 0/0/0). Test doubles therefore fake `get_paginator(...).paginate(...)` with multiple page dicts.
- D2: `types_boto3_dynamodb.client.DynamoDBClient` accepts raw attribute-format payloads (verified for TASK-23.2 with a scratch mypy probe using inline literals). This store builds `dynamodb_item` / `expr_values` as *variables* before the call, so mypy may not infer `AttributeValueTypeDef`. Verify with a scratch probe inside `app/` (`uv run mypy probe.py`, then delete); if it fails, annotate the locals as `dict[str, "AttributeValueTypeDef"]` under `TYPE_CHECKING` rather than adding `# type: ignore`. The same probe should cover `get_paginator("query")` typing for step 9.
- D3: `DynamoDBRetryStore.__init__` gains a required first positional `dynamodb` argument. Grep-verified construction sites: `retry/factory.py:50`, `tests/.../retry/conftest.py:120`, `tests/.../retry/test_dynamodb_store.py:27` — all updated here; nothing else constructs it.
- D4: `classify_aws_error` is called for its classification *and* its propagate-unmapped side effect (same accepted pattern as the shipped idempotency store).
- D5: retry semantics move from `client_next`'s hand-rolled `time.sleep` loop (Throttling / RequestLimitExceeded / ProvisionedThroughputExceeded, 3 attempts) to boto3-native `Config(retries=...)` inside `get_aws_client` — equivalent coverage, no hand-rolled loop, as mandated by decisions/outbound-clients.md. Covered by `tests/unit/integrations/aws/test_aws_client.py`, not re-tested here.
- D6: `integrations/aws/client.py` keeps its own non-`_next` `execute_aws_api_call` / `handle_aws_api_errors` and its `sdk_typing_antipatterns.txt` entry. Only the three `_next` entries are pruned.

## Risks, blast radius, rollback

- R1 (the one intentional behavior change, human-approved — same call as TASK-23.2): an UNMAPPED SDK error now propagates as the raw botocore exception instead of becoming `OperationResult.permanent_error`. Concretely `claim_record`/`fetch_due`/`get_stats`/`get_dlq_entries` can now raise where they previously returned `False`/`[]`/zeros. Mapped codes (including `ConditionalCheckFailedException`, `AccessDeniedException`, throttling, `ResourceNotFoundException`) keep today's outcomes, which is what AC#2 requires. Required by decisions/outbound-clients.md; the only caller path is `retry/worker.py:113,141`, which is not wired in production.
- Blast radius: effectively nil today — `infrastructure/resilience/` has no production importers, `RETRY_BACKEND` defaults to `memory` and is set nowhere in terraform/CI, and `RetryWorker` is never instantiated outside tests. The DynamoDB store's real exposure begins when the retry system is actually wired up; this slice makes that wiring safe rather than fixing live breakage.
- Deleting `client_next.py` also removes the last `_next`-generation `execute_aws_api_call`; `identity_store_next.py` and `dynamodb_next.py` have no remaining importers after step 1 (grep-verified).
- Not touched: `integrations/aws/client.py` (beyond being imported), `integrations/aws/{dynamodb,identity_store,shield}.py`, `infrastructure/idempotency/*`, `infrastructure/storage/*`, `retry/{store,worker,models,config}.py`, terraform, CI workflows, `bin/baselines/deprecated_infra_client_imports.txt`.
- Rollback: single `git revert` — no schema, table, item-shape, attribute-name or configuration change; the same table and the same DynamoDB expressions are used before and after.

## Size gate

Production: 3 files modified (`retry/dynamodb_store.py` ~150 changed LOC, `retry/factory.py` ~8, `audit/service.py` 1 docstring line) + 3 deleted integration modules + 1 baseline file (-3 lines). Tests: 4 deletions, 4 rewrites/repoints. One subsystem (AWS DynamoDB access), no terraform/CI. The bulk of the diff is subtractive, matching the deletion-heavy precedent that reviews quickly. Verdict: fits a single reviewable PR; no decomposition required.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Migrated DynamoDBRetryStore to an injected typed DynamoDB client from integrations.aws.client, with classify_aws_error handling across all former dynamodb_next operations. Restored boto3 dict response handling for due/DLQ reads and paginator-based status totals. Repointed factory and endpoint matrix coverage, removed the three AWS _next dispatcher modules, and ratcheted their SDK typing baseline entries down. Evidence: focused retry and endpoint tests passed (115 passed); retry-store tests passed (31 passed); cache-free mypy on infrastructure/resilience/retry/dynamodb_store.py passed; ruff check passed; bin/check_sdk_typing.py passed; find integrations -name '*_next.py' returned no files; make test passed (user-verified). DoD remaining for human: review the diff and confirm CI quality gates/PR references to decisions/outbound-clients.md and decisions/sdk-typing.md.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-08-31 17:44
---
Human decision 2026-08-31: the fetch_due / get_stats / get_dlq_entries list-vs-dict fix ships INSIDE this migration PR rather than as a separate preceding PR. Rationale: the bug only exists because dynamodb_next.query() force-paginates, so it disappears by construction when the store calls the boto3 client directly - a standalone fix would have to patch code this PR deletes. AC#3 (real-shape response fakes) is the review gate for it.
---

created: 2026-08-31 19:39
---
Planning findings 2026-08-31 (need reviewer confirmation, no AC changes made):
(1) Blast radius is smaller than the task text implies: infrastructure/resilience/ has ZERO production importers (grep over api/infrastructure/jobs/modules/packages/server/main.py), get_resilience_service()/RetryWorker are never called outside the package, RETRY_BACKEND defaults to memory and is set nowhere in terraform/CI, and get_stats/get_dlq_entries have no callers at all. So the list-vs-dict bug is real but currently unreachable - AC#3 is repaying correctness debt before the retry system gets wired, not fixing live breakage.
(2) The bug is worse than described for get_stats specifically: with Select=COUNT the paginated pages carry no Items key, so _paginate_all_results returns an empty list and get_stats silently returns 0/0/0 today. fetch_due and get_dlq_entries instead raise AttributeError, but only when a record actually matches (an empty list is falsy and short-circuits).
(3) Open decision D1 in the plan: after migration get_stats does one query(Select=COUNT) per status, so counts are page-scoped rather than aggregated across pages. Recommended because the method is already documented as approximate and has no callers; say so if you want the get_paginator sum variant instead.
(4) Two items beyond the task's literal scope, both included in the plan: prune the three _next entries from app/bin/baselines/sdk_typing_antipatterns.txt (the sdk-typing freeze baseline is meant to ratchet down), and reword the stale dynamodb_next mention in infrastructure/audit/service.py's module docstring.
---

created: 2026-08-31 21:05
---
Human sign-off 2026-08-31 on the three open planning items: (1) D1 resolved - get_stats uses the get_paginator(query) variant summing page Count across pages (plan step 9 and the test matrix updated accordingly; doubles now fake get_paginator().paginate() with multiple page dicts, incl. a multi-page aggregation test). (2) R1 kept as signed off on TASK-23.2 - unmapped SDK exceptions propagate raw instead of being converted to permanent_error. (3) The two beyond-literal-scope items are confirmed in scope for this PR: pruning the three _next entries from app/bin/baselines/sdk_typing_antipatterns.txt and rewording the stale dynamodb_next mention in infrastructure/audit/service.py's docstring. Plan is now approved and ready for tests-creation / implementation.
---
<!-- COMMENTS:END -->
