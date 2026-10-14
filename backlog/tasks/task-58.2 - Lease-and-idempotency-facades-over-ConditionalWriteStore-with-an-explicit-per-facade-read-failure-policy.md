---
id: TASK-58.2
title: >-
  Lease and idempotency facades over ConditionalWriteStore with an explicit
  per-facade read-failure policy
status: Done
assignee: []
created_date: '2026-10-14 17:45'
updated_date: '2026-10-14 19:07'
labels:
  - infrastructure
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-58.1
parent_task_id: TASK-58
priority: medium
ordinal: 381000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-58 (Stack C layer 3). Builds the per-use facades over the primitive that TASK-58.1 moved; behaviour stays as today.

Decided 2026-10-14 (human):
- The primitive carries no read-failure policy. When the consistent re-read after a contended claim fails, DynamoDB claim() returns a new ClaimResult.INDETERMINATE with no claim token, and each facade maps it. Both facades map it to IN_PROGRESS here (fail-closed), so behaviour is unchanged. This keeps "claim_token is set exactly on NEW" intact; TASK-100 later flips only the lease facade and skips the release when no token is held.
- Each facade takes a required read-failure policy at construction, with no default. The policy enum has only FAIL_CLOSED; TASK-100 adds FAIL_OPEN.
- The facades are pure logic over the Protocol and live in app/contracts/coordination/, importing only the standard library and contracts.
- The idempotency (dedup) facade is built here although it has no production caller until TASK-37.2.
- run_if_leased stays a plain function so TASK-64 can move it mechanically. get_lease_store(ttl) becomes a provider in infrastructure/coordination/factory.py.
- Access Sync's platform_lock and providers, and jobs/scheduled_tasks, use the lease facade; the platform_lock import-linter ignore entry is removed.
- get_idempotency_store and reset_idempotency_store (no production caller) are deleted.
- Facade class names: LeaseStore (lease facade: acquire, release; run_if_leased stays a function) and IdempotencyStore (idempotency facade: claim, complete, release). Lease and idempotency are the industry terms (Kubernetes Lease, Dapr and Redis lock leases; Camel IdempotentRepository, Powertools idempotency) and Store matches RecordStore and JobStatusStore. IdempotencyStore returns with a new meaning one layer after TASK-58.1 renames the primitive away from it; the PR description says so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 LeaseStore (lease) and IdempotencyStore (idempotency) facades in app/contracts/coordination/ wrap ConditionalWriteStore; each is constructed with a required read-failure policy, and both are fail-closed
- [x] #2 The primitive carries no read-failure policy: a failed contended re-read is reported as ClaimResult.INDETERMINATE with no claim token, and the facades map it to IN_PROGRESS
- [x] #3 No second implementation of the conditional-write logic remains, and the DynamoDB own-replay branch is not on the Protocol
- [x] #4 Access Sync and the scheduler use LeaseStore; the platform_lock import-linter ignore entry is removed; get_conditional_write_store and reset_conditional_write_store are deleted
- [x] #5 decisions/reliability.md describes the facades and the per-facade policy, with a dated change entry
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE
Layer 3 of Stack C, after TASK-58.1 (written against the working tree that contains it, uncommitted). Adds the LeaseStore and IdempotencyStore facades over ConditionalWriteStore with a required read-failure policy (FAIL_CLOSED only), adds ClaimResult.INDETERMINATE to the primitive, moves Access Sync and the scheduler onto LeaseStore, and deletes the get/reset singletons. Net runtime behaviour is unchanged: a failed contended re-read still ends as "not acquired" for leases and IN_PROGRESS for dedup. Out of scope: FAIL_OPEN and the release-skip (TASK-100); svcs registration of the coordination contract and any provider for IdempotencyStore (TASK-109); the first IdempotencyStore caller (TASK-37.2); moving run_if_leased into the scheduler registry (TASK-64); the providers -> infrastructure.coordination ignore entry (stays until TASK-124.1). Design decisions on the task (names, INDETERMINATE, FAIL_CLOSED only, required policy, facades in contracts) are taken as given. PR description states that IdempotencyStore returns with a new meaning one layer after TASK-58.1 renamed the primitive away from it.

DESIGN DECISIONS
D1. Primitive. contracts/coordination/store.py: add ClaimResult.INDETERMINATE = "indeterminate". ClaimOutcome docstring keeps "claim_token is set exactly when result is NEW" and adds: INDETERMINATE carries no token and no outcome. The ConditionalWriteStore.claim docstring says INDETERMINATE means the store could not determine whether another claimant holds the key (the consistent re-read after a contended write failed), that the policy for it belongs to the caller, and that production callers go through the facades. The Protocol gains no method and no policy.
D2. DynamoDB. infrastructure/coordination/dynamodb.py claim(): only the classified-error branch of the consistent re-read (current :105-114 region, the except around get_item) returns ClaimOutcome(result=INDETERMINATE). The item-is-None branch stays IN_PROGRESS (the record vanished between put and read: not a read failure). Unclassified errors still raise via classify_aws_error. The own-replay branch stays inside this class, off the Protocol (AC3). The long claim docstring paragraph "Fail-closed re-read ... provisional and lease-scoped ... until TASK-100 flips the policy" is rewritten: the store reports INDETERMINATE and the facade owns the policy. The failed_to_read_idempotency_key warning is kept as is (key, operation already present). InMemoryConditionalWriteStore never emits INDETERMINATE (no failing read) and needs no edit beyond a comment-free pass; confirm.
D3. Policy. New contracts/coordination/policy.py: class ReadFailurePolicy(Enum) with a single member FAIL_CLOSED, and one pure function resolve_indeterminate(outcome: ClaimOutcome, policy: ReadFailurePolicy) -> ClaimOutcome returning ClaimOutcome(result=IN_PROGRESS) for an INDETERMINATE outcome under FAIL_CLOSED and the outcome unchanged otherwise. Written as a match on policy ending in assert_never so TASK-100 adding FAIL_OPEN is a type error until handled. Stdlib only (typing.assert_never, enum).
D4. LeaseStore. New contracts/coordination/lease.py: class LeaseStore(store: ConditionalWriteStore, *, read_failure_policy: ReadFailurePolicy), both required, policy keyword-only with no default. acquire(name) -> str | None: claim, resolve_indeterminate, return claim_token (set only on NEW, so None for IN_PROGRESS, COMPLETED and an INDETERMINATE mapped to IN_PROGRESS). release(name, claim_token) -> bool delegating to store.release, returning False on lost ownership, never raising for it. run_if_leased is NOT in this module: it is lease enforcement (orchestration) and stays a plain function in infrastructure/coordination/lease.py, its body unchanged except it takes a LeaseStore and calls lease_store.acquire/release (decision 2026-10-14; TASK-64 moves it mechanically into server/scheduler). acquire_lease and release_lease free functions are deleted (the LeaseStore methods replace them).
D5. IdempotencyStore. New contracts/coordination/idempotency.py: class IdempotencyStore(store, *, read_failure_policy) with claim(key) -> ClaimOutcome (never INDETERMINATE: resolved through resolve_indeterminate, so FAIL_CLOSED yields IN_PROGRESS with no token, never a re-execution of a possibly completed operation), complete(key, outcome, claim_token) -> bool and release(key, claim_token) -> bool as ownership-checked pass-throughs. No production caller until TASK-37.2; no provider is added here (TASK-109 registers factories; avoiding an unused provider).
D6. Facade shape and boundaries. @final plain classes (typing.final) with __init__, meeting the plugin-architecture.md facade criteria (amended 2026-10-14 in TASK-58.1's PR) (behaviour objects, not entities or I/O models); Protocol-typed dependency only; no logging, no third-party imports (the DynamoDB layer already logs the re-read failure), so the contracts-leaf and stdlib-only import tests keep passing. contracts/coordination/__init__.py re-exports ClaimOutcome, ClaimResult, ConditionalWriteStore, ReadFailurePolicy, LeaseStore, IdempotencyStore with __all__ (no run_if_leased).
D7. Providers. infrastructure/coordination/factory.py: delete get_conditional_write_store, reset_conditional_write_store and the module-level _conditional_write_store_instance (and the now unused get_aws_client call path stays only inside build_). Keep build_conditional_write_store. Add build_lease_store(in_progress_ttl_seconds) -> LeaseStore (wraps build_conditional_write_store with ReadFailurePolicy.FAIL_CLOSED) and move get_lease_store(ttl_seconds) @cache here, returning build_lease_store(...). infrastructure/coordination/lease.py keeps only run_if_leased (acquire_lease, release_lease and get_lease_store leave it); infrastructure/coordination/__init__.py drops acquire_lease, release_lease and the singleton names, exports build_conditional_write_store, build_lease_store, get_lease_store, run_if_leased and the implementations/settings, and its docstring usage example is rewritten around LeaseStore/IdempotencyStore. It still does not re-export contract names.
D8. Policy placement for Access Sync. providers.get_access_sync_lock_store returns LeaseStore built by build_lease_store(in_progress_ttl_seconds=lock_stale_seconds): the policy is chosen in the infrastructure provider, so packages stay free of infrastructure imports except the already-tolerated providers one.
D9. import-linter (app/pyproject.toml no-host-imports): remove "packages.access.sync.platform_lock -> infrastructure.coordination" (it now imports only contracts.coordination). Keep "packages.access.sync.providers -> infrastructure.coordination". Update the shrink-only comment (:265-268): drop the platform_lock clause, keep providers -> infrastructure.coordination removed by TASK-124.1. unmatched_ignore_imports_alerting=error proves the list.

FILE CHANGES (all under /workspace/app; human runs git)
Production, new
- contracts/coordination/policy.py (D3, ~30 LOC)
- contracts/coordination/lease.py (D4, ~55 LOC)
- contracts/coordination/idempotency.py (D5, ~45 LOC)
Production, edited
- contracts/coordination/store.py (D1, ~+12), contracts/coordination/__init__.py (D6, ~+12)
- infrastructure/coordination/dynamodb.py (D2, ~+/-10), infrastructure/coordination/factory.py (D7, net ~-5), infrastructure/coordination/__init__.py (D7, ~-8)
- packages/access/sync/platform_lock.py, providers.py, job_runner.py, ingress.py; jobs/scheduled_tasks.py (call sites below, ~25 LOC)
- pyproject.toml (D9, -1 entry, comment)
Production, deleted
- infrastructure/coordination/lease.py (keeps run_if_leased only, about -25)
Docs
- decisions/reliability.md
Size gate: about 230 production LOC changed (about 180 added, 50 deleted/rewritten), 13 production .py files plus pyproject and one decision record. The file count is over the literal ~10 because five are one to six line import/annotation edits; LOC is far below 400. One subsystem boundary story (coordination contract to its consumers), no mechanical-plus-behaviour mix beyond type-annotation renames forced by the facade, one git revert restores everything. If the reviewer reads the file count as breaching the gate, the fallback split is: 58.2a facades + INDETERMINATE + providers (additive, old helpers kept), 58.2b consumer migration + singleton/lease.py deletion + ignore removal.

TDD STEPS
1. Write failing tests first (red = ImportError or failed assertion).
   a. tests/unit/contracts/coordination/test_coordination_policy.py, test_coordination_lease_store.py, test_coordination_idempotency_store.py: use a scripted fake ConditionalWriteStore (frozen outcomes per call, records calls) so INDETERMINATE can be injected; plus an InMemoryConditionalWriteStore-backed block for real lifecycle. See TEST MATRIX.
   b. Edit tests/unit/contracts/coordination/test_coordination_contracts_imports.py: __all__ set now includes the four new names, ClaimResult members include INDETERMINATE, AST scan still stdlib/contracts-only over the new modules.
   c. Edit tests/unit/infrastructure/coordination/test_coordination_dynamodb_store_operations.py: the classified re-read-failure case (currently asserts IN_PROGRESS near :145-153) now asserts INDETERMINATE with claim_token None and outcome None; the unclassified-error-raises case, the item-None case (IN_PROGRESS) and the own-replay-to-NEW case stay as they are.
   d. Edit test_coordination_store_factory.py: delete the get/reset singleton tests (:25-58); keep the build_conditional_write_store TTL test; add build_lease_store and get_lease_store tests (moved from test_coordination_lease_helpers.py).
   e. Rewrite test_coordination_lease_helpers.py as test_coordination_lease_store.py under tests/unit/contracts/coordination/ for the acquire/release cases (single winner, release then reacquire, foreign token keeps lease, concurrent single winner), and keep the run_if_leased cases (run/skip/exception/expired takeover/taken-over-mid-run) in tests/unit/infrastructure/coordination/test_coordination_run_if_leased.py, both unchanged in intent; the get_lease_store singleton-per-ttl cases move to the factory test file. Delete the old file.
   f. Edit consumer tests (below) and test_coordination_legacy_path_removed.py (infrastructure.coordination no longer has acquire_lease, release_lease, get_conditional_write_store, reset_conditional_write_store; contract names still not re-exported).
   Confirm red.
2. contracts/coordination: store.py (D1), policy.py, lease.py, idempotency.py, __init__.py.
3. infrastructure/coordination: dynamodb.py (D2), factory.py and __init__.py (D7), trim lease.py to run_if_leased.
4. Migrate consumers, edit pyproject (D9), edit decisions/reliability.md.
5. Green run, then the gates.

CALL-SITE EDITS (app/ relative)
- packages/access/sync/platform_lock.py:5-6 -> `from contracts.coordination import LeaseStore` only (drop the infrastructure.coordination import); lock_store annotations :20, :42 -> LeaseStore; acquire_lock body :31 `acquire_lease(lock_store, lock_key)` -> `lock_store.acquire(lock_key)`; release_lock body :49 `release_lease(lock_store, lock_key, claim_token)` -> `lock_store.release(lock_key, claim_token)`. Docstring module line "shared infrastructure lease primitive" -> "coordination lease facade".
- packages/access/sync/providers.py:3,5 `ConditionalWriteStore`/`build_conditional_write_store` -> `from contracts.coordination import LeaseStore` + `from infrastructure.coordination import build_lease_store`; :26 return annotation LeaseStore; :28 body build_lease_store(in_progress_ttl_seconds=...). Docstring "lock store" kept.
- packages/access/sync/job_runner.py:27 import and annotations :58, :141, :252, :300 ConditionalWriteStore -> LeaseStore (job_runner passes lock_store only to release_lock; :135 and :241 unchanged).
- packages/access/sync/interactions/ingress.py:17 import and annotations :57, :141 -> LeaseStore.
- jobs/scheduled_tasks.py:12 -> `from infrastructure.coordination import get_lease_store, run_if_leased` (import line unchanged); :82-87 _tier2 body unchanged (get_lease_store(ttl_seconds) now returns a LeaseStore).
- packages/access/sync/interactions/http.py:145 and slack.py:178,272 call get_access_sync_lock_store() and pass the object through: no edit.
- Test edits: tests/unit/packages/access/sync/test_platform_lock.py:11-19 and test_access_sync_routes.py:11,65-71 and test_access_sync_ingress_lock_token.py:13,26-28 (_lock_store/_store helpers return LeaseStore(InMemoryConditionalWriteStore(settings=...), read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)); test_providers.py:94,127 patch target -> packages.access.sync.providers.build_lease_store, assert the returned object is the patched return; tests/unit/jobs/test_scheduled_tasks.py:12,237-239,252-254,271-273,391-392 (mock_get_lease_store.return_value becomes a LeaseStore over the in-memory store); tests/unit/infrastructure/configuration/test_settings_delegation.py and tests/unit/infrastructure/coordination/test_coordination_settings.py: they reference reset_conditional_write_store, switch to the settings reset only (check at implementation what each used it for; if only singleton hygiene, drop the call).
- Final sweep: rg -n "acquire_lease|release_lease|get_conditional_write_store|reset_conditional_write_store|infrastructure.coordination.lease" app decisions bin must return nothing; rg for "ConditionalWriteStore" in packages/ and jobs/ must return nothing (they use the facade).

DECISIONS EDITS (AC5)
- decisions/reliability.md: in the "Three primitives" paragraph (line 16) replace "facades follow in TASK-58.2"-style wording with the facade statement: LeaseStore (acquire, release) and IdempotencyStore (claim, complete, release) are thin facades over ConditionalWriteStore in contracts/coordination, each constructed with a required read-failure policy; the primitive reports ClaimResult.INDETERMINATE (no token) when the contended re-read fails and carries no policy; both facades are FAIL_CLOSED today (lease: not acquired; dedup: IN_PROGRESS); the policy is per use because a failed re-read is tolerable for a lease over idempotent bodies but would re-execute a completed operation for dedup (TASK-100 flips only the lease). Update the line-32 lease-helper sentence: the lease semantics live in the LeaseStore facade (contracts/coordination/lease.py), which becomes "the one place" acquire/release is implemented; run_if_leased stays in app/infrastructure/coordination/lease.py as the host's lease enforcement; get_lease_store/build_lease_store in factory.py replace the build_conditional_write_store TTL mention; update Migration: TASK-58.2 facades done, tolerated list keeps "features importing infrastructure.coordination directly instead of resolving the contract from the registry" (providers entry, TASK-124.1/TASK-109); add Changes entry dated 2026-10-14: facades, policy, INDETERMINATE, singleton deletion, platform_lock ignore removed (TASK-58.2). Check the Checks section line about conformance and add the INDETERMINATE facade check.
- decisions/plugin-architecture.md: the facade criteria and the 2026-10-14 entry already landed in TASK-58.1's PR; verify LeaseStore/IdempotencyStore meet them, no edit expected. cloud-portability.md: grep for IdempotencyStore/lease helper names; edit only if found (none expected).

TEST MATRIX
Files (unit, tests/unit/contracts/coordination/): test_coordination_policy.py, test_coordination_lease_store.py, test_coordination_idempotency_store.py; (unit, infrastructure): test_coordination_dynamodb_store_operations.py (edited), test_coordination_store_factory.py (edited).
- Policy: FAIL_CLOSED maps INDETERMINATE to IN_PROGRESS with no token and no outcome; NEW, COMPLETED (outcome preserved) and IN_PROGRESS pass through untouched.
- Construction: LeaseStore(store) and IdempotencyStore(store) without read_failure_policy raise TypeError; policy is keyword-only; there is no default.
- LeaseStore happy: first acquire returns a token, second returns None, release by holder returns True and the name is acquirable again. Boundary: expired lease is taken over; a COMPLETED record yields None. Failure/ownership: INDETERMINATE (scripted store) yields None and release is never called by run_if_leased; foreign token release returns False and keeps the lease; run_if_leased releases on job exception; a lease taken over mid-run is not released by the stale holder; concurrent acquire has exactly one winner.
- IdempotencyStore happy: claim NEW then complete then claim returns COMPLETED with outcome; release then claim returns NEW. Failure: INDETERMINATE becomes IN_PROGRESS, token None, so the caller cannot proceed and never sees INDETERMINATE; complete/release with a foreign token return False; IN_PROGRESS passes through. A scripted COMPLETED + failed-reread sequence documents why fail-closed is the dedup-safe default.
- DynamoDB: classified re-read failure returns INDETERMINATE; unclassified re-read error still raises; item-None stays IN_PROGRESS; conformance suites on both stores are unchanged (INDETERMINATE not produced by either in the happy paths).
- Providers: build_lease_store returns a LeaseStore whose store is a DynamoDBConditionalWriteStore with the TTL override; get_lease_store caches per ttl; the access providers test patches build_lease_store.
- Import surface: contracts __all__ exact set; new modules import only stdlib and contracts; check-fake-coverage and lint-imports unchanged-or-better.
Route changes: none, so no new route tests; existing Access Sync route and ingress tests keep passing on LeaseStore.

AC TRACEABILITY
AC1: steps 1a, 1b, 2 (D3-D6; test_coordination_lease_store.py, test_coordination_idempotency_store.py, test_coordination_policy.py construction and FAIL_CLOSED cases, test_coordination_contracts_imports.py). AC2: steps 1a, 1c, 2, 3 (D1-D3; test_coordination_dynamodb_store_operations.py INDETERMINATE case, policy and both facade INDETERMINATE-to-IN_PROGRESS cases). AC3: D2, D5 (dynamodb own-replay test unchanged, Protocol shape test test_coordination_store_protocol.py unchanged: still three methods; rg shows the only claim() body is the two existing stores). AC4: steps 1d, 1e, 1f, 3, 4 (test_platform_lock.py, test_providers.py, test_scheduled_tasks.py, test_coordination_legacy_path_removed.py, test_coordination_store_factory.py, final rg sweep, uv run lint-imports with the entry removed). AC5: DECISIONS EDITS (rg over decisions/ for the dated 2026-10-14 TASK-58.2 entry and the policy statement). No AC rewrite is needed: 58.1 changed names but the ACs are already stated in the new names.

ASSUMPTIONS AND DOUBTS
- Assumes 58.1 is committed on the branch below before implementation starts; verify git state at start (working tree currently holds its edits uncommitted).
- Assumes nothing outside the listed files calls get_conditional_write_store/reset_conditional_write_store or acquire_lease/release_lease: verified by rg 2026-10-14 over app, decisions, bin; re-run in the final sweep. test_settings_delegation.py and test_coordination_settings.py mention the reset helper; verify whether it is the settings reset or the store reset.
- Assumes ClaimResult is not matched exhaustively anywhere in production (rg shows only infrastructure/coordination and tests); a new member therefore breaks no match statement. Verify with mypy on touched files.
- Assumes the in-memory store never needs to emit INDETERMINATE and that the fake-coverage checker ignores non-Protocol classes (the facades are not Protocols); verify with make check-fake-coverage.
- run_if_leased stays in infrastructure/coordination/lease.py (decided 2026-10-14): publishing it in contracts/ only to deprecate it when TASK-64 moves it to server/scheduler would add churn to the public API.
- jobs/scheduled_tasks.py importing from both contracts and infrastructure is allowed (jobs is not in the no-host-imports source list); verify with lint-imports.
- No IdempotencyStore provider is added, so it has no construction path in app code until TASK-109/TASK-37.2; tests construct it directly. Confirm this is acceptable to TASK-37.2's plan.
- A mapped INDETERMINATE is silent in the facade (contracts cannot log); the DynamoDB warning remains the only signal. Operators lose nothing compared with today.

GATES (from app/)
uv run ruff check . ; uv run ruff format --check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files; repo-wide errors elsewhere ignored); uv run pytest tests --ignore=tests/smoke ; make check-fake-coverage (expect OK, 6 baselined gaps, no baseline edit) ; uv run lint-imports (expect one fewer ignore, 0 broken, no unmatched-ignore error). Record outputs in notes.

BLAST RADIUS AND ROLLBACK
Touches the Access Sync lock path and the three Tier-2 scheduler leases, plus the primitive's claim() return set. A wrong import or signature fails at import time or in the existing Access Sync and scheduler tests, not silently. Runtime behaviour on the failed-re-read path is the only semantic hop (IN_PROGRESS to INDETERMINATE to IN_PROGRESS through the facade) and is pinned by tests on both sides; any direct caller of ConditionalWriteStore.claim added later must handle INDETERMINATE (docstring says so; the facades are the sanctioned callers). No data, schema, terraform or env change. One git revert restores everything. Ordering: TASK-58.1 committed first; TASK-100 later edits only the LeaseStore policy and ReadFailurePolicy; TASK-109 registers ConditionalWriteStore and later the facades; TASK-64 moves run_if_leased from contracts/coordination/lease.py; TASK-37.2 constructs IdempotencyStore with FAIL_CLOSED.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the approved plan (TDD: new tests red on ImportError first, then green).

What changed
- contracts/coordination: ClaimResult.INDETERMINATE (no token, no outcome); policy.py (ReadFailurePolicy.FAIL_CLOSED, resolve_indeterminate with assert_never); lease.py (LeaseStore: acquire, release); idempotency.py (IdempotencyStore: claim, complete, release). Both @final, policy keyword-only and required, no logging, stdlib/contracts imports only. __init__ exports the six names.
- infrastructure/coordination: DynamoDB claim() returns INDETERMINATE only on a classified re-read failure; item-None stays IN_PROGRESS; unclassified still raises; own-replay branch unchanged. factory.py: get/reset_conditional_write_store and the module singleton deleted; build_lease_store (FAIL_CLOSED) and @cache get_lease_store added. lease.py holds only run_if_leased(lease_store, ...). acquire_lease/release_lease deleted.
- Consumers: Access Sync platform_lock (contracts only), providers (build_lease_store), job_runner and ingress annotations use LeaseStore; jobs/scheduled_tasks unchanged (get_lease_store now returns LeaseStore).
- pyproject: platform_lock -> infrastructure.coordination ignore entry removed, shrink-only comment updated.
- decisions/reliability.md: facade and per-facade policy statement, lease paragraph, new Checks line, Migration, 2026-10-14 Changes entry.

Tests
- New: tests/unit/contracts/coordination/{conftest.py (ScriptedConditionalWriteStore stub + in-memory fixtures), test_coordination_policy.py, test_coordination_lease_store.py, test_coordination_idempotency_store.py}; tests/unit/infrastructure/coordination/test_coordination_run_if_leased.py (incl. INDETERMINATE: no job, no release).
- Edited: contracts imports (__all__), store protocol (ClaimResult has four members), DynamoDB operations (INDETERMINATE case + new vanished-record IN_PROGRESS case), store factory (singleton tests dropped; build_lease_store TTL and FAIL_CLOSED, get_lease_store per-TTL cache), legacy path removed (removed helpers and singleton), Access Sync platform_lock/routes/ingress-lock-token/providers, jobs scheduled_tasks.
- Deleted: test_coordination_lease_helpers.py (cases split into lease store and run_if_leased tests).
- Plan doubt resolved: test_settings_delegation.py and test_coordination_settings.py never referenced the store singleton; no edit.

Gates (2026-10-14, from app/)
- uv run ruff check . : All checks passed. ruff format --check: 917 files already formatted.
- uv run pytest tests --ignore=tests/smoke : 4868 passed.
- uv run mypy . : 48 errors in 19 files, 0 in touched files (all in modules/, i18n, resilience, configuration docs_generator, incident adapters, integrations; same count as layer 2).
- make check-fake-coverage : OK, 6 baselined gaps, no baseline edit.
- uv run lint-imports : 10 kept, 0 broken, no unmatched-ignore error after removing the entry.
- Sweep: rg acquire_lease|release_lease|get_conditional_write_store|reset_conditional_write_store over app, decisions, bin hits only the legacy-path-removed test; no ConditionalWriteStore in packages/ or jobs/.

PR description must say IdempotencyStore returns with a new meaning (dedup facade) one layer after TASK-58.1 renamed the primitive away from it.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 17:54
---
2026-10-14 (human): facade names are LeaseStore and IdempotencyStore (chosen over LeaseProvider/IdempotentRepository, which clash with this codebase's providers.py and have no repository precedent here).
---

created: 2026-10-14 18:31
---
2026-10-14 (human): plan approved as one PR (size gate accepted). Facades LeaseStore and IdempotencyStore (@final) and ReadFailurePolicy live in contracts/coordination/; run_if_leased stays in infrastructure/coordination/lease.py until TASK-64. The plugin-architecture.md amendment allowing pure facades in contracts/ lands with TASK-58.1. No IdempotencyStore provider here; TASK-109 covers registration. The facades do not log; the DynamoDB re-read warning (key, operation) is the signal until TASK-100 adds a policy-outcome log at the caller.
---
<!-- COMMENTS:END -->
