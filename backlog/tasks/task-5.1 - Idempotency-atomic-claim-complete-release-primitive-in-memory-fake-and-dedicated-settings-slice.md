---
id: TASK-5.1
title: >-
  Idempotency: atomic claim/complete/release primitive, in-memory fake, and
  dedicated settings slice
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-24 17:57'
updated_date: '2026-07-24 19:08'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies: []
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - decisions/configuration.md
parent_task_id: TASK-5
priority: high
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational slice of the TASK-5 decomposition (see TASK-5 for full rationale). Scoped to app/infrastructure/idempotency/ only; does NOT touch any caller.

Aligns with decisions/reliability.md (Idempotency), decisions/cloud-portability.md (contract 4 - in-memory fake as standing second provider), decisions/configuration.md (Ownership + incremental-migration clause).

Steps:
1. Define IdempotencyStore Protocol + ClaimResult (NEW/COMPLETED/IN_PROGRESS) in app/infrastructure/idempotency/protocol.py. No DynamoDB vocabulary (no ConditionExpression parameters) in the Protocol surface.
2. Rewrite app/infrastructure/idempotency/dynamodb.py's claim using PutItem with ConditionExpression attribute_not_exists(pk), status IN_PROGRESS with a bounded in-progress TTL. ConditionalCheckFailed branches: COMPLETED -> return recorded outcome; IN_PROGRESS unexpired -> concurrent duplicate, reject/defer; IN_PROGRESS expired -> claimant crashed, take over and re-execute. complete() records the outcome; release() deletes so redelivery retries.
3. New key format: plain f"{feature}:{intent}:{idempotency_id}" string formatting. No hashing utility of any kind.
4. New in-memory fake implementing the same Protocol (the standing second provider per decisions/cloud-portability.md contract 4).
5. Migrate idempotency settings NOW, in this same change: new app/infrastructure/idempotency/settings.py (IdempotencySettings + get_idempotency_settings()); delete app/infrastructure/configuration/infrastructure/idempotency.py and its exports from that package's __init__.py. This is not TASK-24 scope - it is an orphaned legacy-settings-home instance that decisions/configuration.md's incremental-migration rule requires to move with whatever work touches the domain.
6. Delete app/infrastructure/idempotency/key_builder.py and IdempotencyKeyBuilder - verified dead code (grep shows zero real call sites, only self-export and its own docstring). Remove its export from infrastructure/idempotency/__init__.py.
7. Shared Protocol-conformance test suite run against both the DynamoDB implementation (moto) and the fake, covering: the concurrency case (two concurrent identical claims -> exactly one NEW and one IN_PROGRESS/COMPLETED, asserted via the conditional-write path not timing) and the key-format rule.

Explicit exclusion: do NOT touch callers yet. Old IdempotencyService/DynamoDBIdempotencyService/cache.py/service.py/factory.py's get_idempotency_service() stay in place untouched so existing callers (job_runner.py, platform_lock.py, interactions/http.py, interactions/slack.py, interactions/ingress.py, integrations/slack/utils.py) keep working unmodified until their own subtasks land. This is the one deliberate exception to 'no dead code left behind' in this decomposition - it is transitional and closed out by the job-status-extraction subtask.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IdempotencyStore Protocol exists in app/infrastructure/idempotency/protocol.py with claim/complete/release and ClaimResult (NEW/COMPLETED/IN_PROGRESS); no vendor types or vendor query syntax in its signatures
- [x] #2 DynamoDB implementation's claim() uses ConditionExpression attribute_not_exists(pk); grep shows no get-then-put pattern remains in app/infrastructure/idempotency/dynamodb.py
- [x] #3 Concurrency test: two concurrent identical claims yield exactly one NEW and one IN_PROGRESS/COMPLETED outcome, asserted via the conditional-write path, not timing
- [x] #4 In-memory fake implements the same Protocol and passes the shared conformance test suite alongside the DynamoDB implementation (moto)
- [x] #5 Keys follow {feature}:{intent}:{idempotency_id}; no payload hash, no truncation (key-format test); IdempotencyKeyBuilder and key_builder.py are deleted
- [x] #6 IdempotencySettings/get_idempotency_settings() live in app/infrastructure/idempotency/settings.py; app/infrastructure/configuration/infrastructure/idempotency.py and its exports are deleted
- [x] #7 Old IdempotencyService/DynamoDBIdempotencyService/cache.py/service.py/factory.py/get_idempotency_service() remain untouched and functional for existing callers (transitional exception, closed out by the job-status-extraction subtask)
- [x] #8 A get_idempotency_store() singleton provider (with a reset_idempotency_store() test helper) exists in app/infrastructure/idempotency/factory.py returning the DynamoDB-backed IdempotencyStore, matching the existing get_idempotency_service()/get_cache() pattern, so TASK-5.2/TASK-5.3 have something concrete to depend on
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Shared Protocol-conformance suite passes against both the DynamoDB implementation (moto) and the in-memory fake
- [ ] #2 No caller migrations included in this PR; existing callers of get_idempotency_service() continue to pass their current tests unmodified
- [ ] #3 PR references decisions/reliability.md, decisions/cloud-portability.md, decisions/configuration.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Research summary (grounding)

Current app/infrastructure/idempotency/ contents (all read in full):
- protocol.py: existing IdempotencyService Protocol (get/set/clear/get_stats/cache) - stays untouched, new Protocol added alongside it.
- cache.py: IdempotencyCache ABC (get/set/clear/get_stats) - stays untouched (AC#7).
- dynamodb.py: DynamoDBCache(IdempotencyCache) using get_item/put_item/delete_item/scan from integrations.aws.dynamodb_next, table sre_bot_idempotency, PK idempotency_key - stays untouched; new class added to same file.
- service.py: DynamoDBIdempotencyService - stays untouched (AC#7).
- factory.py: get_cache()/reset_cache()/get_idempotency_service() - stay untouched; new provider added.
- key_builder.py: IdempotencyKeyBuilder - zero real call sites confirmed via repo-wide grep (only its own self-export in __init__.py and its own docstring) - dead code, delete per step 6.
- __init__.py: re-exports all of the above.

Old settings home: app/infrastructure/configuration/infrastructure/idempotency.py defines IdempotencySettings(IDEMPOTENCY_TTL_SECONDS, default 3600) + get_idempotency_settings() (lru_cache). Re-exported from app/infrastructure/configuration/infrastructure/__init__.py:7-24.

Exact import call sites of the old settings path (must repoint or delete, all within this task's boundary - none are caller business logic):
- app/infrastructure/idempotency/dynamodb.py:9
- app/infrastructure/idempotency/factory.py:5
- app/tests/integration/infrastructure/idempotency/conftest.py:7
- app/tests/unit/infrastructure/idempotency/conftest.py:7
- app/tests/unit/infrastructure/idempotency/test_narrow_slice.py:7
- app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py:7 (generic infra-settings-singleton test file; contains a TestIdempotencySettingsSingleton class that must move to the idempotency-owned test dir since the settings module is leaving infrastructure/configuration/infrastructure/)

Existing callers of get_idempotency_service()/IdempotencyService (confirmed via grep, NOT touched by this task per explicit exclusion and AC#7):
app/packages/access/sync/interactions/http.py:18, interactions/ingress.py:17, interactions/slack.py:17, job_runner.py:25, platform_lock.py (4 refs), app/integrations/slack/utils.py::legacy_slack_listener (uses IdempotencyService transitively, not a direct import - confirmed no reference to old settings path there).

Reference implementation precedent for atomic conditional-write claim/lease already exists in this repo: app/infrastructure/resilience/retry/dynamodb_store.py::claim_record (PutItem/UpdateItem with ConditionExpression "attribute_not_exists(claim_worker) OR claim_expires_at < :now", branching on result.error_code == "ConditionalCheckFailedException") and app/infrastructure/resilience/retry/store.py::InMemoryRetryStore (threading.Lock-guarded dict). This task's DynamoDBIdempotencyStore/InMemoryIdempotencyStore mirror this established pattern rather than inventing a new one. RetrySettings.claim_lease_seconds (default 300) is the naming/value precedent for the new in-progress TTL field.

integrations.aws.dynamodb_next.put_item/get_item/delete_item forward **kwargs to boto3 (confirmed by reading client_next.py execute_aws_api_call), so ConditionExpression/ExpressionAttributeNames/ExpressionAttributeValues pass through unchanged - no changes needed to dynamodb_next.py or client_next.py. On ClientError, _handle_final_error returns OperationResult.permanent_error(message=str(e), error_code=e.response["Error"]["Code"]) - confirmed this is how ConditionalCheckFailedException surfaces to callers (matches the existing retry-store pattern exactly).

terraform/dynamodb.tf:86-101 confirms table sre_bot_idempotency already exists with hash_key idempotency_key and a ttl block on attribute "ttl" - reused as-is, table is schemaless beyond the key so new attributes (status, in_progress_expires_at, outcome_json, claimed_at, completed_at) need no terraform change. No terraform touched by this task.

IMPORTANT open conflict discovered (see Assumptions/Doubts #1): the task's AC#4/DoD#1 say the DynamoDB side of the conformance suite should run "(moto)", but moto is not currently a dependency anywhere in app/pyproject.toml, and decisions/testing.md instead names "DynamoDB-Local... marked slow" as the sanctioned real-semantics test mechanism. Neither is currently wired into CI (.github/workflows/ci_code.yml's `make test` has no dynamodb-local service container, and no `slow` marker is registered or excluded). The existing tests in this exact package (app/tests/integration/infrastructure/idempotency/test_dynamodb_cache_integration.py) use a third pattern: patching infrastructure.idempotency.dynamodb.put_item/get_item directly with scripted OperationResult values - fast but does not validate real DynamoDB ConditionExpression syntax/semantics. Recommendation (adopted below, flagged for human override): add moto[dynamodb] as a new dev-only dependency. It requires no CI/workflow changes (in-process emulation, no external service), fits the <500ms integration budget, and is the only option of the three that actually validates the ConditionExpression string against real conditional-write semantics - which is the entire point of AC#3's concurrency assertion. This avoids crossing into terraform/CI subsystems and keeps the change inside app/.

Size estimate and gate verdict

Production files touched: protocol.py (edit/add), dynamodb.py (edit/add), in_memory.py (new), settings.py (new), factory.py (edit/add), __init__.py (edit exports), key_builder.py (delete), configuration/infrastructure/idempotency.py (delete), configuration/infrastructure/__init__.py (edit remove 4-6 lines), pyproject.toml (1-line dev-dependency add) = 10 files, additive/expansive in nature (old code paths untouched, nothing deleted that's still referenced), estimated ~350-400 production LOC (most of it net-new: two new store classes + settings file), single subsystem (app/infrastructure/idempotency + its settings counterpart), no mechanical-refactor+behavior-change mixing (this step IS the "expand" slice per TASK-5's own decomposition), single git revert cleanly removes the addition since no caller depends on the new Protocol yet. Verdict: fits one reviewable PR - no further decomposition needed (TASK-5's parent-level decomposition already did the necessary split).

Ordered implementation steps

1. app/infrastructure/idempotency/settings.py (NEW): IdempotencySettings(InfrastructureSettings) with IDEMPOTENCY_TTL_SECONDS (moved from old location, default 3600, completed-record TTL) and new IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS (default 300, bounded in-progress claim TTL per decisions/reliability.md, naming/value precedent from RetrySettings.claim_lease_seconds) + get_idempotency_settings() with @lru_cache(maxsize=1), matching the exact pattern of the file being replaced.
2. Delete app/infrastructure/configuration/infrastructure/idempotency.py. Edit app/infrastructure/configuration/infrastructure/__init__.py to remove its import block (lines 7-10) and its two __all__ entries.
3. app/infrastructure/idempotency/protocol.py: add (alongside the untouched existing IdempotencyService Protocol) - ClaimResult(Enum): NEW/COMPLETED/IN_PROGRESS; ClaimOutcome (@dataclass(frozen=True)): result: ClaimResult, outcome: dict[str, Any] | None = None; IdempotencyStore(Protocol, runtime_checkable): claim(key: str) -> ClaimOutcome, complete(key: str, outcome: dict[str, Any]) -> None, release(key: str) -> None. No vendor types/params in any signature (AC#1).
4. app/infrastructure/idempotency/dynamodb.py: repoint the IdempotencySettings import to the new settings.py (step 1). Add DynamoDBIdempotencyStore(idempotency_settings: IdempotencySettings, table_name: str = IDEMPOTENCY_TABLE) implementing IdempotencyStore, reusing the existing PARTITION_KEY constant:
   - claim(key): single PutItem with ConditionExpression "attribute_not_exists(#pk) OR (#status = :in_progress AND #expires_at < :now)" (ExpressionAttributeNames for #pk/#status/#expires_at, ExpressionAttributeValues for :in_progress/:now), status=IN_PROGRESS, in_progress_expires_at=now+IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS, ttl=same bound (so stray IN_PROGRESS rows still expire from the table). On success -> ClaimOutcome(NEW). On ConditionalCheckFailedException -> one get_item to classify: status COMPLETED -> ClaimOutcome(COMPLETED, outcome=json.loads(outcome_json)); status IN_PROGRESS (or item vanished mid-race) -> ClaimOutcome(IN_PROGRESS). Any other error_code -> raise RuntimeError (mirrors DynamoDBRetryStore's raise-on-unexpected-failure convention). This satisfies AC#2 (attribute_not_exists(pk) used; no get-then-put chain - the get_item only happens after a failed write, purely for response classification, not for deciding whether to write).
   - complete(key, outcome): unconditional PutItem with status=COMPLETED, outcome_json=json.dumps(outcome), ttl=now+IDEMPOTENCY_TTL_SECONDS.
   - release(key): delete_item(key) so redelivery hits the attribute_not_exists branch.
5. app/infrastructure/idempotency/in_memory.py (NEW): InMemoryIdempotencyStore(idempotency_settings: IdempotencySettings) implementing IdempotencyStore with a threading.Lock-guarded dict[str, dict], same claim/complete/release semantics as the DynamoDB store (expired-IN_PROGRESS takeover computed by comparing stored expiry to time.time()), mirroring InMemoryRetryStore's structure (app/infrastructure/resilience/retry/store.py).
6. app/infrastructure/idempotency/factory.py: repoint the IdempotencySettings import to the new settings.py. Add get_idempotency_store() -> IdempotencyStore (module-level singleton, same _instance-global pattern as get_cache()) constructing DynamoDBIdempotencyStore(idempotency_settings=get_idempotency_settings()), plus reset_idempotency_store() test-reset helper mirroring reset_cache(). Leave get_cache()/reset_cache()/get_idempotency_service() untouched (AC#7).
7. app/infrastructure/idempotency/__init__.py: add exports for IdempotencyStore, ClaimResult, ClaimOutcome, DynamoDBIdempotencyStore, InMemoryIdempotencyStore, get_idempotency_store, reset_idempotency_store, IdempotencySettings, get_idempotency_settings; remove the IdempotencyKeyBuilder import/export only.
8. Delete app/infrastructure/idempotency/key_builder.py.
9. app/pyproject.toml: add "moto[dynamodb]" to [project.optional-dependencies].dev (pinned exact version resolved via `uv add --dev`), run `uv lock`/`uv sync --extra dev` to refresh the lockfile.
10. Test file updates (repoint-only, no behavior change): app/tests/unit/infrastructure/idempotency/conftest.py:7, app/tests/unit/infrastructure/idempotency/test_narrow_slice.py:7, app/tests/integration/infrastructure/idempotency/conftest.py:7 - repoint import to infrastructure.idempotency.settings. app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py - remove TestIdempotencySettingsSingleton class and its now-orphaned import.
11. app/tests/unit/infrastructure/idempotency/test_idempotency_settings.py (NEW): the moved TestIdempotencySettingsSingleton tests (from step 10) plus new coverage for IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS default/env-read.
12. app/tests/unit/infrastructure/idempotency/test_idempotency_store_protocol.py (NEW): runtime_checkable/isinstance shape tests for IdempotencyStore against both new store classes and a minimal fake; asserts ClaimOutcome is frozen; asserts no vendor-shaped parameter names in IdempotencyStore's signatures (AC#1).
13. app/tests/unit/infrastructure/idempotency/test_in_memory_store.py (NEW): InMemoryIdempotencyStore unit tests (isolated, no I/O).
14. app/tests/integration/infrastructure/idempotency/conftest.py: add moto fixtures - dummy AWS credential env vars via monkeypatch.setenv, a fixture that opens moto's mock_aws(), creates a throwaway table (e.g. "test-sre-bot-idempotency", same key schema as terraform/dynamodb.tf:86-101), and yields a DynamoDBIdempotencyStore bound to it.
15. app/tests/integration/infrastructure/idempotency/test_idempotency_store_conformance.py (NEW): shared parametrized suite (fixture parametrized over [in-memory store, moto-backed DynamoDB store]) - see Test Matrix below. This is the suite required by AC#4/DoD#1.

AC-to-step-to-test traceability

AC#1 (Protocol, no vendor types) -> step 3 -> test_idempotency_store_protocol.py::test_no_vendor_parameters_in_signatures, test_protocol_is_runtime_checkable
AC#2 (ConditionExpression attribute_not_exists; no get-then-put) -> step 4 -> test_idempotency_store_conformance.py::test_claim_new_key_uses_conditional_put (asserts on mocked/moto call, checks ConditionExpression content) + manual grep verification during finalization (grep -n "get_item" app/infrastructure/idempotency/dynamodb.py confirms the only get_item call is post-failure classification, not a pre-write check)
AC#3 (concurrency test via conditional-write path) -> step 4/15 -> test_idempotency_store_conformance.py::test_concurrent_identical_claims_yield_one_new_one_conflict (deterministic: seed one claim, then issue a second claim() call for the same key and assert ClaimResult.IN_PROGRESS while a fresh key claim in parallel asserts ClaimResult.NEW - no threads/timing)
AC#4 (in-memory fake passes shared suite alongside DynamoDB/moto) -> steps 5,14,15 -> test_idempotency_store_conformance.py parametrization
AC#5 (key format, no hash/truncation; key_builder deleted) -> steps 4,5,8 -> test_idempotency_store_conformance.py::test_claim_preserves_exact_key_no_hash_no_truncation; absence of key_builder.py verified at step 8
AC#6 (settings moved) -> steps 1,2,6 -> test_idempotency_settings.py
AC#7 (old stack untouched) -> no code step (explicit non-change) -> re-run existing app/tests/unit/infrastructure/idempotency/{test_cache.py,test_factory.py,test_idempotency_protocol.py} and app/tests/integration/infrastructure/idempotency/test_dynamodb_cache_integration.py unmodified and confirm they still pass, plus existing tests for job_runner.py/platform_lock.py/interactions/{http,ingress,slack}.py/integrations/slack/utils.py unmodified and passing (regression check, no new test authored)
New AC (provider function, added below) -> step 6 -> test_factory.py-equivalent addition or covered inside test_idempotency_store_conformance.py fixture construction via get_idempotency_store()

Test matrix (test_idempotency_store_conformance.py, parametrized over both implementations)

- Happy path: claim() on unseen key -> ClaimResult.NEW; complete(key, outcome) then claim() again -> ClaimResult.COMPLETED with the exact recorded outcome dict.
- Boundary: claim() while an unexpired IN_PROGRESS record exists for the same key -> ClaimResult.IN_PROGRESS (reject/defer).
- Boundary: claim() after the existing IN_PROGRESS record's TTL has elapsed (simulated via a pre-seeded expiry timestamp in the past, no real sleep) -> ClaimResult.NEW (crashed-claimant takeover).
- Failure/idempotency: release(key) after a failed attempt, then claim() again -> ClaimResult.NEW (redelivery retries cleanly).
- Concurrency (AC#3): two claim() calls against the identical key, sequenced deterministically (second call issued only after the first's write is confirmed) -> exactly one NEW and one IN_PROGRESS/COMPLETED; asserted via ClaimResult, not elapsed time.
- Key format (AC#5): claim() with a key containing multiple colons and non-ASCII/long segments round-trips unchanged when read back (no internal hash/truncate).

Assumptions and doubts

1. moto[dynamodb] vs DynamoDB-Local vs mocked dynamodb_next (see Research summary) - recommendation is moto, adopted in this plan; flagged for explicit human override since it adds a new dev dependency and the task's own AC/DoD wording already says "(moto)" while decisions/testing.md documents DynamoDB-Local. Verify: human confirms moto is acceptable, or redirects to DynamoDB-Local (would require also wiring a service container into .github/workflows/ci_code.yml - out of this task's file-count budget and would flip the gate verdict).
2. IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS default of 300s is a new value not specified by the task or decisions/reliability.md (which only says "bounded"); chosen to match RetrySettings.claim_lease_seconds precedent. Verify: acceptable default, or product wants a different bound.
3. ClaimOutcome/ClaimResult placement and shape (frozen dataclass + plain Enum) is a design choice consistent with type-model-boundaries (Protocol for behavior, dataclass(frozen=True) for the internal result entity) and OperationStatus's plain-Enum precedent; not dictated verbatim by the task text beyond "ClaimResult (NEW/COMPLETED/IN_PROGRESS)". Verify: no caller in TASK-5.2/5.3 already assumes a different shape (checked TASK-5.2's description - only says "using the IdempotencyStore from TASK-5.1", no shape assumed).
4. A get_idempotency_store()/reset_idempotency_store() provider pair is being added even though no caller in this task uses it, because TASK-5.2 depends on TASK-5.1 and its own text says "using the IdempotencyStore from TASK-5.1" - something obtainable must exist. Proposed as a new AC below rather than silently added.
5. ConditionalCheckFailedException on the new store's claim() will log at ERROR severity via the shared client_next.py::_handle_final_error path for what is an expected, frequent outcome (concurrent duplicate rejection) - this is a pre-existing shared-infra logging behavior, not something this task's scope permits changing (would touch app/integrations/aws/client_next.py, used by every AWS caller in the codebase). Flagged as an accepted, out-of-scope consequence, not fixed here.
6. Table reuse: the new store writes to the same sre_bot_idempotency table/PK as the untouched DynamoDBCache, using different secondary attributes (status/in_progress_expires_at/outcome_json vs. response_json/operation_type). Verified no attribute-name collisions and no terraform change needed (table is schemaless beyond the declared hash key).

Blast radius and rollback

Purely additive/expansive change: no existing import path is removed except the deleted configuration/infrastructure/idempotency.py (whose only consumers are being repointed in the same PR) and key_builder.py (verified zero real callers). No existing caller of get_idempotency_service()/IdempotencyService/DynamoDBCache is modified. A single git revert of this PR fully restores prior behavior with no follow-up cleanup required, since nothing outside app/infrastructure/idempotency/ and its own test tree depends on the new Protocol/classes yet. Worst-case risk if this ships wrong: the new, unused-by-callers store code has a latent bug that only surfaces once TASK-5.2/5.3/5.4 start consuming it - caught by those subtasks' own test suites before any production caller is migrated. No deployment ordering constraints (no new env vars required at runtime beyond the existing IDEMPOTENCY_TTL_SECONDS; the new IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS has a safe default).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the idempotency primitive slice in app/infrastructure/idempotency with a new vendor-agnostic IdempotencyStore Protocol (claim/complete/release), ClaimResult enum, and frozen ClaimOutcome dataclass. Added DynamoDBIdempotencyStore with conditional PutItem claim semantics (attribute_not_exists(pk) OR stale IN_PROGRESS takeover), plus complete() and release(). Added InMemoryIdempotencyStore with matching claim/complete/release semantics and in-progress expiry takeover.\n\nMigrated settings ownership to infrastructure.idempotency.settings (IdempotencySettings + get_idempotency_settings with IDEMPOTENCY_TTL_SECONDS and IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS). Removed legacy infrastructure/configuration/infrastructure/idempotency.py and removed legacy exports from infrastructure/configuration/infrastructure/__init__.py.\n\nAdded get_idempotency_store()/reset_idempotency_store() singleton provider helpers in infrastructure/idempotency/factory.py while preserving get_cache()/reset_cache()/get_idempotency_service() behavior for existing callers. Deleted dead key_builder.py and removed IdempotencyKeyBuilder export from infrastructure/idempotency/__init__.py.\n\nTest evidence:\n- uv run pytest tests/unit/infrastructure/idempotency tests/integration/infrastructure/idempotency -q => 105 passed\n- uv run pytest tests --ignore=tests/smoke -q => 2924 passed, 37 skipped\n- uv run ruff check . => passed\n- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' => fails with pre-existing baseline errors outside idempotency scope (123 errors in 43 files), no errors reported in touched idempotency files.\n\nAdditional follow-on test updates were required so full-suite collection reflected the migrated settings location: tests/unit/infrastructure/configuration/test_settings_delegation.py and test_settings_structure.py now import idempotency settings from infrastructure.idempotency.settings.\n\nDoD items left for human verification:\n- Confirm PR references decisions/reliability.md, decisions/cloud-portability.md, decisions/configuration.md in review metadata.\n- Human final review of baseline mypy debt status and whether to accept existing non-task type-check failures.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 18:24
---
Planning note: AC#4/DoD#1 say the DynamoDB side of the conformance suite runs '(moto)'. moto is not currently a repo dependency; decisions/testing.md instead names DynamoDB-Local (marked slow) as the sanctioned real-semantics mechanism, and neither is wired into .github/workflows/ci_code.yml today (no service container, no slow-marker exclusion). The existing tests in this exact package instead patch infrastructure.idempotency.dynamodb.put_item/get_item directly with scripted OperationResult values. Plan adopts moto[dynamodb] as a new dev-only test dependency (no CI/workflow changes needed, in-process emulation, actually validates the ConditionExpression string) - flagging for explicit human sign-off before implementation since it introduces a new dependency and could instead be redirected to DynamoDB-Local (which would need a CI service container and likely trip the single-PR gate).
---

created: 2026-07-24 18:31
---
Follow-up: the moto-vs-DynamoDB-Local conflict noted above has been split out to TASK-50 (Reconcile decisions/testing.md with moto for AWS SDK test substitution), since it's a cross-cutting testing-tooling decision, not specific to idempotency. Correction to the earlier framing: moto is not a brand-new tool introduction - it was already explicitly blessed for boto3 substitution in the legacy docs/adr/testing-standards.md ('moto for AWS service substitution where the SDK ... require server-side semantics that pure stubs cannot reproduce'), which decisions/testing.md's migration silently dropped in favor of DynamoDB-Local-only wording. TASK-5.1's conformance-suite step should track TASK-50's decision rather than re-litigate it.
---
<!-- COMMENTS:END -->
