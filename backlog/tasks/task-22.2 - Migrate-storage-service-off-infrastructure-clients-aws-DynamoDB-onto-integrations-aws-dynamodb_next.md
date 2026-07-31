---
id: TASK-22.2
title: >-
  Migrate storage service off infrastructure/clients/aws DynamoDB onto
  integrations/aws/dynamodb_next
status: To Do
assignee: []
created_date: '2026-07-29 21:10'
updated_date: '2026-07-31 16:58'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.1
  - TASK-70
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/infrastructure/storage/service.py
  - app/integrations/aws/shield.py
parent_task_id: TASK-22
priority: high
ordinal: 105000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-22 (parent). Repoint infrastructure/storage/service.py off get_aws_clients().dynamodb (infrastructure/clients/aws) onto integrations/aws/dynamodb_next.

Call sites in infrastructure/storage/service.py: get_storage_service() (line ~262) resolves get_aws_clients().dynamodb and injects a DynamoDBClient into DynamoDBStorageService; the service calls self._dynamodb.put_item/get_item/delete_item/query. dynamodb_next.py exposes MODULE-LEVEL functions put_item(table_name, Item=...), get_item, update_item, delete_item, query returning OperationResult — the injection shape changes from a client object to module functions. Preserve DynamoDBStorageService's public method surface and OperationResult behavior exactly (serialize/deserialize, ConditionExpression, pagination via query force_paginate). Wire consumers to dynamodb_next as it exists today (do NOT rename the _next suffix — that is downstream TASK-23; do NOT apply the raise/classify contract — that is downstream TASK-25).

Test migration: keep storage tests in tests/unit/infrastructure/storage/ (already unit-located); ADD unit tests for the dynamodb_next path under tests/unit/integrations/aws/ (there is currently NO test_dynamodb_next). If test_client_next.py in tests/integrations/aws/ is touched, relocate it to tests/unit/integrations/aws/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/storage/service.py no longer imports infrastructure.clients.aws; DynamoDBStorageService is backed by a typed boto3 client from integrations/aws get_aws_client("dynamodb") and turns SDK exceptions into OperationResult via classify_aws_error - no per-service wrapper class, no dynamodb_next dependency
- [ ] #2 All existing tests/unit/infrastructure/storage/ tests pass with identical OperationResult outcomes per method (behavior-neutral at the StorageService Protocol boundary), including ConditionalCheckFailedException -> success(data=False) and query auto-pagination; the StorageService Protocol/public method surface is unchanged
- [ ] #3 integrations/aws exposes get_aws_client + classify_aws_error with unit coverage under tests/unit/integrations/aws/ (each mapped botocore/ClientError family -> expected status/error_code/retry_after; one unmapped exception propagates); dynamodb_next is left untouched for its other consumers (idempotency, resilience) and no new *_next module is introduced
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral at the StorageService Protocol boundary: OperationResult outcomes identical; PR references decisions/layers.md, decisions/outbound-clients.md, and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEQUENCED (2026-07-31, decisions/sdk-typing.md): this slice now migrates storage DIRECTLY onto the target shape (typed boto3 client + classify), instead of onto the dynamodb_next dispatcher. It absorbs the DynamoDB portions of the old TASK-23 (rename) and TASK-25 (raise/classify) so storage is touched ONCE. See the TASK-22 umbrella comment for the full rationale.

GROUNDING (re-verify at implementation): infrastructure/storage/service.py:19 imports `from infrastructure.clients.aws import get_aws_clients` + a TYPE_CHECKING DynamoDBClient hint; get_storage_service() (@cache) builds DynamoDBStorageService(get_aws_clients().dynamodb). The service body calls self._dynamodb.get_item/put_item/delete_item/query, and relies on the facade wrapper's auto-pagination (query passes keys=["Items"], force_paginate=True). Storage is a FACADE consumer today - it is NOT on dynamodb_next. dynamodb_next has its OWN separate consumers (idempotency store, resilience retry store) that are out of scope here and are converged later (TASK-23/TASK-25). Existing storage tests construct DynamoDBStorageService(dynamodb=MagicMock()) directly, so the constructor stays injectable.

TARGET SHAPE (decisions/outbound-clients.md + sdk-typing.md):
1. Establish the single AWS construction+classification primitive in integrations/aws: get_aws_client(service_name) - a factory configuring SDK-native resilience ONCE (botocore Config(retries={"mode": "standard"}), connect/read timeouts, region, and the existing DynamoDB-Local endpoint gate for ENVIRONMENT in {local,dev,ci} -> http://dynamodb-local:8000) and returning a boto3 client typed via types-boto3 (annotate `client: DynamoDBClient` under TYPE_CHECKING) - and classify_aws_error(exc) -> (OperationStatus, error_code, retry_after) mapping EXPECTED botocore families only (ResourceNotFoundException -> NOT_FOUND; ConditionalCheckFailedException -> preserved as today's error_code so callers' string check still works; Throttling/RequestLimitExceeded/ProvisionedThroughputExceededException -> TRANSIENT_ERROR w/ retry_after; AccessDenied/UnauthorizedException -> UNAUTHORIZED; everything else PROPAGATES, not classified). Extract both from integrations/aws/shield.py's Config + _classify_client_error. Place in integrations/aws/client.py; VERIFY at implementation whether legacy integrations/aws/client.py content has live consumers and converge-or-defer per grounding (do NOT delete shield.py here - other AWS services still use it until TASK-25).
2. Rework DynamoDBStorageService to hold the typed client from get_aws_client("dynamodb") and call boto3 methods directly inside try/except+classify_aws_error, returning OperationResult with OUTCOMES IDENTICAL to today. The service (the adapter/boundary) now owns pagination explicitly via client.get_paginator("query") aggregating Items - replacing the facade wrapper's keys/force_paginate. Update get_storage_service() DI accordingly; keep the constructor injectable (tests pass a fake/typed double).
3. Do NOT touch dynamodb_next.py, client_next.py, or the facade tree here (facade deletion is TASK-22.5; dispatcher deletion is TASK-23; shield deletion + remaining AWS services are TASK-25).

WHY behavior-neutral is now "at the Protocol boundary": the service body DOES change (direct boto3 + explicit paginator + classify), unlike the old shim approach, but every StorageService OperationResult outcome is preserved. This is verified by the existing storage tests (unchanged assertions) plus new classify_aws_error unit tests, not by a zero-diff body. This is the deliberate resequencing trade: one deeper, correct change instead of shim-now + rewrite-twice.

STEPS:
1. Add integrations/aws/client.py: get_aws_client + classify_aws_error (extract from shield.py). Add types-boto3[dynamodb] usage (TASK-70 provides the dep). Unit tests under tests/unit/integrations/aws/test_aws_client.py (factory: Config retries + endpoint gate; classify: each mapped family + one unmapped-propagates). Reuse/extend tests/unit/integrations/aws/test_dynamodb_local_endpoint.py coverage for the factory.
2. Rework infrastructure/storage/service.py: drop infrastructure.clients.aws imports; inject get_aws_client("dynamodb"); implement get/put/delete/query directly with try/except+classify and an explicit query paginator; update module + class docstrings to cite integrations/aws + decisions/sdk-typing.md. Keep StorageService Protocol and get_storage_service() signature unchanged.
3. Keep storage tests' assertions unchanged; adapt only the injected double if its call surface changed (it now receives a boto3-client-shaped double, or the service constructs the client internally via the factory - prefer factory-injection so tests can pass a typed fake). Preserve test_existing_item_returns_false (ConditionalCheckFailedException -> success(False)).

AC-TO-STEP: AC#1 -> Steps 1-2 (grep infrastructure.clients returns nothing; service holds typed client + classify). AC#2 -> Step 3 (storage tests green, outcomes identical, pagination + conditional-write preserved). AC#3 -> Step 1 (get_aws_client/classify_aws_error + tests; dynamodb_next untouched, grep-verified). DoD#1 -> full suite + ruff/mypy clean + PR cites layers.md/outbound-clients.md/sdk-typing.md.

TEST MATRIX: happy (get/put/delete/query outcomes identical to facade path); pagination (query aggregates multi-page Items via paginator, same result as force_paginate); conditional write (ConditionalCheckFailedException -> success(False), error_code string preserved); classify (NOT_FOUND/TRANSIENT+retry_after/UNAUTHORIZED families; unmapped KeyError propagates); endpoint gate (local/dev/ci -> dynamodb-local, staging/prod no override). Commands: cd app && uv run pytest tests/unit/infrastructure/storage tests/unit/integrations/aws -v; then tests --ignore=tests/smoke; then ruff check . and mypy (must resolve the typed dynamodb client).

BLAST RADIUS / ROLLBACK: contained to storage service internals + a new integrations/aws/client.py; StorageService Protocol, get_storage_service() signature, and every StorageService consumer are untouched. Single git revert restores the facade-backed path. get_aws_client/classify_aws_error are additive (do not disturb shield.py, dynamodb_next, or their consumers). Ordering: requires TASK-70 (stubs + pattern) and TASK-22.1; independent of 22.3/22.4 except that 22.3 REUSES get_aws_client/classify_aws_error built here.

SIZE GATE: one new integrations/aws/client.py (~80 LOC) + storage service rework (~1 file) + 2 test files. One vendor surface, single reviewable PR - within the gate.

DOUBTS (flag, verify at impl): (a) exact classify mapping must reproduce the facade/executor OperationResult outcomes storage currently observes - diff infrastructure/clients/aws/executor.py::_map_client_error against shield's _classify_client_error and pick the mapping storage tests assert; (b) whether get_aws_client belongs in integrations/aws/client.py vs a new module given the legacy client.py - grep consumers before placing; (c) confirm no StorageService consumer branches on a fine-grained status echoed from storage (grep OperationStatus. in audit/service.py, access sync/request) - prior grounding says none do.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-31 16:15
---
Planning finding: tests/unit/integrations/aws/test_dynamodb_next.py already exists (added by other work since this task was written) and already covers get/put/update/delete/query/scan on dynamodb_next, incl. query's pagination kwargs. This task's Description line 'there is currently NO test_dynamodb_next' is stale. Plan does not duplicate that file; new coverage this task adds targets the new _DynamoDBNextBackend adapter in service.py instead. AC#3's 'relocate touched tests/integrations/aws files' clause is not triggered by this task's diff (client_next.py/dynamodb_next.py stay unmodified) - left AC#3 wording as-is since it's still correct, just conditionally a no-op here.
---

created: 2026-07-31 16:26
---
Correction to plan Doubt #2: repo-wide search initially missed .devcontainer/docker-compose.yml, which DOES define a real dynamodb-local sibling service (container_name: dynamodb-local, port 9000->8000) with the devcontainer's app service set to ENVIRONMENT=dev and depends_on dynamodb-local; app/Makefile also runs .devcontainer/dynamodb-create.sh to bootstrap tables matching terraform/dynamodb.tf. Three independent modules (integrations/aws/client_next.py, integrations/aws/dynamodb.py, modules/aws/aws_access_requests.py) already hardcode the same ENVIRONMENT in (local,dev,ci) -> http://dynamodb-local:8000 gate, covered by a dedicated cross-module test (tests/unit/integrations/aws/test_dynamodb_local_endpoint.py) that also asserts staging/production get no override. staging has zero implemented behavior anywhere beyond being a literal ENVIRONMENT option (grep-confirmed against decisions/*.md and app code) - matches human confirmation that local-endpoint routing is intended for every non-production environment today. CONCLUSION: doubt #2 is resolved, not a risk - dynamodb_next's local-endpoint gating is the established, live, tested convention; this migration converges storage-service onto it (previously the legacy path only did so if a developer manually set AWS_ENDPOINT_URL, an easy-to-miss manual opt-in) rather than introducing new/unproven behavior. No plan changes needed.
---

created: 2026-07-31 16:58
---
RESEQUENCED per the SDK-typing research (decisions/sdk-typing.md, new 2026-07-31). Original plan wired storage onto integrations/aws/dynamodb_next via a throwaway _DynamoDBNextBackend shim whose only job was to paper over dynamodb_next.query()'s duplicate keys/force_paginate kwargs - i.e. it ADDED a micro-wrapper in a sprint whose thesis is REMOVING wrappers, then TASK-23 (rename) and TASK-25 (raise/classify) would have rewritten the same file twice more. New plan migrates storage ONCE, directly onto the target shape (typed boto3 client via types-boto3 + get_aws_client factory + classify_aws_error), absorbing the DynamoDB portions of TASK-23 and TASK-25.

AC CHANGES (for human review at the task-breakdown checkpoint): AC#1 retargeted from "backed by integrations/aws/dynamodb_next" to "backed by a typed boto3 client from get_aws_client + classify_aws_error (no wrapper, no dynamodb_next dep)". AC#2 reworded from "unchanged assertions / zero-diff body" to "identical OperationResult outcomes at the StorageService Protocol boundary" - the service body now changes (direct boto3 + explicit paginator + classify), but outcomes are preserved (behavior-neutral at the boundary, not zero-diff). AC#3 retargeted from "dynamodb_next unit coverage" to "get_aws_client + classify_aws_error coverage; dynamodb_next left untouched for its idempotency/resilience consumers". DoD#1 gains a decisions/sdk-typing.md reference.

Dependency added: TASK-70 (types-boto3 + sdk-typing guardrails) is now a prerequisite. dynamodb_next is intentionally NOT deleted here - it retains non-facade consumers (idempotency store, resilience retry store) that TASK-23/TASK-25 converge onto the same get_aws_client/classify_aws_error primitive established by this slice.
---
<!-- COMMENTS:END -->
