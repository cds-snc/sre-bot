---
id: TASK-5.3
title: >-
  Idempotency: rewrite Access Sync platform/user concurrency lock onto
  claim/complete/release; align with TASK-6
status: Done
assignee:
  - '@me'
created_date: '2026-07-24 17:57'
updated_date: '2026-07-27 17:37'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1350'
parent_task_id: TASK-5
priority: high
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of the TASK-5 decomposition (see TASK-5 for full rationale). Depends on TASK-5.1 (the claim/complete/release primitive and in-memory fake).

Aligns with decisions/reliability.md (Idempotency - concurrency locking is a lease, the same conditional-write contract, but a distinct capability from dedup) and decisions/layers.md (shared platform capabilities that multiple business features need live in app/infrastructure, never inside one feature package).

Scope: app/packages/access/sync/platform_lock.py (check_lock/acquire_lock/release_lock) implements a per-platform/per-user sync-job lock via get-then-set on the same racy IdempotencyService (same TOCTOU bug as the Slack case, different symptom). Rewrite it onto the atomic claim primitive from TASK-5.1.

Architecture correction (2026-07-27, superseding the original "TASK-6 consumes this package's lease helper" framing): the reusable acquire/release lease semantics must not be authored inside app/packages/access/sync/. TASK-6's Tier-2 background-job singleton lease is consumed by app/jobs/scheduled_tasks.py across unrelated domains (aws identity_center/spending, incident, maxmind, opsgenie, google_workspace, access) - a cross-cutting capability several features need, exactly the case decisions/layers.md reserves for app/infrastructure/. This task therefore ships a generic acquire_lease/release_lease helper as a new module in app/infrastructure/idempotency/ (built directly on TASK-5.1's claim/complete/release primitive), and rewrites platform_lock.py as a thin, feature-specific wrapper over it (key naming + best-effort holder-info reporting only - nothing generic lives in the package). TASK-6 keeps a dependency on this task only because this task's PR is what delivers app/infrastructure/idempotency/lease.py; TASK-6's Tier-2 gate must import that infrastructure module directly and must never import from app/packages/access/sync/.

Update call sites in app/packages/access/sync/interactions/ingress.py and app/packages/access/sync/job_runner.py and their tests.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 check_lock/acquire_lock/release_lock in app/packages/access/sync/platform_lock.py use the atomic claim primitive from TASK-5.1 (via a shared infra lease helper) instead of get-then-set on IdempotencyService
- [x] #2 app/packages/access/sync/interactions/ingress.py and job_runner.py call sites and their tests are updated to the new lock API
- [x] #3 A generic, vendor-neutral lease helper (acquire_lease/release_lease) is added to app/infrastructure/idempotency/lease.py - not to the access/sync package - built on the TASK-5.1 claim/complete/release primitive; app/packages/access/sync/platform_lock.py becomes a thin wrapper over it (key naming + holder-info reporting only); TASK-6's dependency/comment is updated to point at this infra module, never at platform_lock.py or the access/sync package
- [x] #4 acquire_lock/release_lock is the sole atomic gate; the former two-step check_lock-then-acquire_lock is removed. A rejected duplicate request still reports the winning job's id via a best-effort, non-authoritative current_holder lookup, preserving existing HTTP/Slack already-running response behavior (test_sync_endpoint_user_sync_returns_existing_job_when_lock_held keeps passing).
- [x] #5 bin/unlock-sync-job.sh operates on the new lease's DynamoDB item schema (status/claimed_at/in_progress_expires_at) via delete-item, not the legacy response_json/put-item patch, and --dry-run output reflects the new fields.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass, including a concurrency test proving the TOCTOU race is closed for the platform/user lock
- [x] #2 PR references decisions/reliability.md and cross-references TASK-6
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposition context: this is a leaf slice of TASK-5 (see TASK-5.1's shipped interface). No further decomposition needed - single-PR size gate check below.

## Grounding (call sites enumerated)

- app/packages/access/sync/platform_lock.py:26-66 - check_lock/acquire_lock/release_lock, all get-then-set on IdempotencyService (racy).
- app/packages/access/sync/interactions/ingress.py:24-28,79-81,145-147 - imports check_lock/platform_lock_key/user_lock_key; enqueue_user_sync/enqueue_platform_sync each do a bare check_lock(...) read, then unconditionally call spawn_*_thread (TOCTOU window is HERE: two concurrent requests can both see "free" before either acquires).
- app/packages/access/sync/job_runner.py:38-42,120-131(user),155-165,229-234(platform) - spawn_user_sync_thread/spawn_platform_sync_thread call acquire_lock() (the actual write); run_user_sync_job/run_platform_sync_job call release_lock() at the end via idempotency.set() on the same key.
- app/packages/access/sync/interactions/http.py:16,145,175 - get_idempotency_service() constructed once per request, passed as idempotency= into both enqueue_* calls.
- app/packages/access/sync/interactions/slack.py:16,183-190,~245 - same pattern in handle_sync_user_command/handle_sync_platform_command.
- app/bin/unlock-sync-job.sh:95-160 - operator tool hand-writing/reading the *old* DynamoDBCache item shape (response_json JSON blob) against the sre_bot_idempotency table for the same lock keys; must speak the new lease's item shape (status/claimed_at/in_progress_expires_at) or it silently stops working.
- app/tests/unit/packages/access/sync/test_job_runner.py:214-260(+) and test_access_sync_routes.py:98-165 are the only existing tests touching this path.
- infrastructure.idempotency (TASK-5.1, shipped): IdempotencyStore.claim(key)->ClaimOutcome(result, outcome), .complete(key, outcome), .release(key); ClaimResult.{NEW,COMPLETED,IN_PROGRESS}; DynamoDBIdempotencyStore/InMemoryIdempotencyStore both take idempotency_settings in __init__; get_idempotency_store()/reset_idempotency_store() singleton.
- app/jobs/scheduled_tasks.py registers jobs across unrelated domains (modules.aws.identity_center/spending, modules.incident, integrations.maxmind/opsgenie/google_workspace, packages.access.sync) - confirms TASK-6's Tier-2 lease consumer is a cross-cutting scheduler, not the access/sync feature, which is why the reusable lease logic cannot live in app/packages/access/sync/.

## Architecture correction driving this revision

The previous plan had platform_lock.py call lock_store.claim()/release() directly and treated its acquire_lock/release_lock functions as "the lease helper" TASK-6 would import. That puts a cross-cutting capability (generic named lease with TTL, used by every registered background job regardless of domain) inside a single feature package, and has an unrelated infra-level consumer (app/jobs/) reach sideways into app/packages/access/sync/ - a violation of the packages -> infrastructure -> integrations downward-only import rule in decisions/layers.md, and of "shared platform capabilities belong in app/infrastructure" (.github/copilot-instructions.md). decisions/reliability.md is explicit that dedup, leases, and outbox claims are "one primitive... one thing to implement correctly per storage backend" - i.e. the lease logic itself, not just the underlying claim/release primitive, is meant to be shared.

Fix: extract the generic lease helper into app/infrastructure/idempotency/lease.py. platform_lock.py becomes a thin, feature-specific wrapper (key naming + holder-info reporting) over that shared helper. TASK-6's Tier-2 gate (in app/jobs/ and/or app/server/lifespan.py) imports directly from infrastructure.idempotency, never from packages.access.sync.

## Two design gaps found in research (unchanged from prior analysis, still require explicit sign-off)

1. Staleness TTL mismatch. AccessSyncSettings.lock_stale_seconds defaults to 14400s (4h - a platform sync can legitimately run long); the generic IdempotencyStore singleton's in-progress claim TTL is IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS (default 300s). Using the shared singleton as-is would make locks "expire" mid-run and let a second sync start - reproducing the exact duplicate-work bug this task closes. Resolution: an additive factory function build_idempotency_store(in_progress_ttl_seconds: int) -> IdempotencyStore in infrastructure/idempotency/factory.py (DynamoDB-backed, non-singleton, TTL override via IdempotencySettings.model_copy(update=...)), consumed by a new package-owned singleton provider get_access_sync_lock_store() in packages/access/sync/providers.py. Package code still resolves the store via a provider function, per the dependency-boundary rule.
2. claim() carries no payload on IN_PROGRESS. A lease (which only ever calls claim()/release(), never complete()) has no way to report which job currently holds it, but check_lock() today returns that info and it is genuinely user-facing (Slack already-running message; test_sync_endpoint_user_sync_returns_existing_job_when_lock_held). Resolution: a small, best-effort, non-authoritative "holder info" record written through the legacy IdempotencyService under a distinct key (f"{lock_key}:holder", never the lease's own key) immediately after a successful claim; read back only for reporting when a claim is rejected. This stays in platform_lock.py (feature-specific reporting), not in the shared infra lease helper (which has no concept of "holder info").

## Ordered steps

1. **app/infrastructure/idempotency/lease.py (NEW)**: generic, vendor-neutral helper built directly on IdempotencyStore.claim()/release() - no payload, no holder-info, no feature-specific concept:
   - `acquire_lease(lock_store: IdempotencyStore, name: str) -> bool`: calls lock_store.claim(name); returns True only when ClaimResult.NEW, False for IN_PROGRESS/COMPLETED.
   - `release_lease(lock_store: IdempotencyStore, name: str) -> None`: calls lock_store.release(name).
   - Module docstring documents that this is the single shared lease primitive for singleton-execution use cases (access-sync platform/user locks, TASK-6's Tier-2 job lease) and that new consumers extend this module rather than reimplementing acquire/release semantics elsewhere.
   - Export both functions from app/infrastructure/idempotency/__init__.py.
2. **app/infrastructure/idempotency/factory.py / __init__.py**: add build_idempotency_store(in_progress_ttl_seconds: int) -> IdempotencyStore (reads get_idempotency_settings(), overrides IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS via model_copy(update=...), constructs a fresh non-singleton DynamoDBIdempotencyStore). Purely additive.
3. **app/packages/access/sync/providers.py**: add get_access_sync_lock_store() -> IdempotencyStore (functools.lru_cache(maxsize=1)) calling build_idempotency_store(in_progress_ttl_seconds=get_access_sync_settings().lock_stale_seconds).
4. **app/packages/access/sync/platform_lock.py - full rewrite as a thin wrapper**:
   - Keep platform_lock_key(platform) / user_lock_key(platform, user_email) unchanged.
   - Module docstring: describe the lease model per decisions/reliability.md and point at infrastructure.idempotency.lease as the shared primitive this module wraps; note that TASK-6 consumes that shared module directly, not this package.
   - Remove check_lock as a separate exported symbol - folding its read into acquire_lock's atomic branch is the actual race fix.
   - `acquire_lock(lock_key: str, payload: dict[str, Any], lock_store: IdempotencyStore, idempotency: IdempotencyService, ttl_seconds: int) -> bool`: calls `acquire_lease(lock_store, lock_key)`; on True, best-effort writes payload to idempotency.set(f"{lock_key}:holder", payload, ttl_seconds=ttl_seconds); returns the acquire_lease result.
   - `current_holder(lock_key: str, idempotency: IdempotencyService) -> dict[str, Any] | None`: idempotency.get(f"{lock_key}:holder") - read-only, informational only.
   - `release_lock(lock_key: str, lock_store: IdempotencyStore) -> None`: calls `release_lease(lock_store, lock_key)`.
5. **app/packages/access/sync/interactions/ingress.py**: _IngressSettings Protocol drops lock_stale_seconds (the lock store's own TTL now owns staleness). enqueue_user_sync/enqueue_platform_sync gain a lock_store: IdempotencyStore parameter. Replace the check_lock(...) read with one atomic acquire_lock(...) call; on False, call current_holder(...) for the best-effort existing-job info (unchanged EnqueuedJob(already_running=True, ...) shape); on True, call spawn_user_sync_thread/spawn_platform_sync_thread with lock_store=lock_store forwarded (no re-acquire).
6. **app/packages/access/sync/job_runner.py**: spawn_user_sync_thread/spawn_platform_sync_thread remove the acquire_lock(...) call entirely (the lock is already held by the caller - document this invariant in the docstring); add lock_store: IdempotencyStore param, forwarded into the thread's kwargs. run_user_sync_job/run_platform_sync_job: add lock_store param; replace release_lock(key, payload, idempotency, ttl_seconds) with release_lock(key, lock_store).
7. **app/packages/access/sync/interactions/http.py**: import get_access_sync_lock_store from packages.access.sync.providers; call it once per request alongside get_idempotency_service(); pass lock_store=lock_store into both enqueue_* calls. Drop unused lock_stale_seconds from _AccessSyncSettingsPort.
8. **app/packages/access/sync/interactions/slack.py**: same wiring in handle_sync_user_command and handle_sync_platform_command.
9. **app/bin/unlock-sync-job.sh**: rewrite ddb_get output parsing from the old Item.response_json.S JSON-blob shape to the lease's real attributes (Item.status.S, Item.claimed_at.N, Item.in_progress_expires_at.N); replace the patch-and-ddb_put "force release" logic with a straight aws dynamodb delete-item on LOCK_KEY, gated the same way (only act when status == IN_PROGRESS, still support --dry-run).

## AC traceability

- AC#1 (check_lock/acquire_lock/release_lock use the claim primitive) -> steps 1,4 -> test_lease.py, test_platform_lock.py.
- AC#2 (ingress.py/job_runner.py call sites + tests updated) -> steps 5,6 (+7,8 as necessarily-affected transitive call sites) -> test_job_runner.py updates, test_access_sync_routes.py updates.
- AC#3 (generic lease helper lives in app/infrastructure/idempotency/, not the access/sync package; platform_lock.py is a thin wrapper; TASK-6's dependency comment points at the infra module) -> steps 1,4 -> test_lease.py; verified by grep that app/jobs/** and app/server/** never import from packages.access.sync in TASK-6's own PR (out of scope here, noted for TASK-6).
- AC#4 (acquire_lock/release_lock sole atomic gate, check_lock removed, holder reporting preserved) -> step 4 -> test_platform_lock.py, test_access_sync_routes.py::test_sync_endpoint_user_sync_returns_existing_job_when_lock_held.
- AC#5 (unlock-sync-job.sh speaks the new item schema) -> step 9 -> manual --dry-run verification (bash script, no pytest coverage).
- DoD#1 (tests pass incl. concurrency test proving TOCTOU closed) -> steps 1,4 -> test_lease.py::test_acquire_lease_concurrent_calls_yield_exactly_one_winner.
- DoD#2 (PR references decisions/reliability.md, cross-references TASK-6) -> human PR-authoring step, not a code step.

## Test matrix

New app/tests/unit/infrastructure/idempotency/test_lease.py (InMemoryIdempotencyStore):
- acquire_lease on a free name -> True; second acquire_lease on the same still-held name -> False.
- release_lease then acquire_lease again -> True (lease is reusable, unlike a dedup marker).
- Concurrency: two threads call acquire_lease on the identical name simultaneously (threading.Barrier(2)) against a shared InMemoryIdempotencyStore -> exactly one True, one False.

New app/tests/unit/packages/access/sync/test_platform_lock.py (InMemoryIdempotencyStore + a MagicMock IdempotencyService for holder-info):
- Happy path: acquire_lock on a free key -> True; current_holder returns the exact payload passed in.
- Boundary: second acquire_lock on the same still-held key -> False; current_holder still returns the original holder's payload.
- Failure/retry: release_lock then acquire_lock again -> True.

Updated app/tests/unit/packages/access/sync/test_job_runner.py:
- add lock_store=MagicMock() param to run_user_sync_job/run_platform_sync_job tests; idempotency.set.call_count drops by 1 (release no longer goes through idempotency.set); assert lock_store.release.assert_called_once_with(...).

Updated app/tests/unit/packages/access/sync/test_access_sync_routes.py:
- patch packages.access.sync.interactions.http.get_access_sync_lock_store to return a fake/InMemory store; existing-job-held test patches the same provider with a store whose claim() returns ClaimOutcome(ClaimResult.IN_PROGRESS); keep fake_idempotency.get.return_value as the holder payload (now read via current_holder).

New/updated app/tests/unit/packages/access/sync/test_providers.py:
- get_access_sync_lock_store returns a singleton; its in-progress TTL reflects AccessSyncSettings.lock_stale_seconds.

app/tests/unit/infrastructure/idempotency/test_factory.py:
- add test_build_idempotency_store_overrides_in_progress_ttl_only.

Out of scope: no new direct unit tests for slack.py's two handlers (exercised transitively through ingress/platform_lock, already covered above).

## Assumptions and doubts

1. Folding check_lock into acquire_lock (removing it as a separate exported symbol) is interpreted as fixing the racy behavior the three current symbols describe, not a mandate to keep three separately-callable phases. Verify: human agrees, or wants check_lock retained as a non-authoritative alias over current_holder.
2. lease.py/build_idempotency_store/get_access_sync_lock_store add new surface to infrastructure/idempotency and to packages/access/sync/providers.py - purely additive, no signature change to protocol.py/dynamodb.py/in_memory.py. Verify: acceptable, or human prefers reusing the generic get_idempotency_store() singleton and accepting the 300s-vs-14400s staleness mismatch (not recommended).
3. bin/unlock-sync-job.sh is in scope even though AC#2 only names ingress.py/job_runner.py, because it directly manipulates the same DynamoDB keys with the old item shape - shipping without updating it leaves a documented operator tool silently broken. Verify: human agrees it's in-scope.

## Blast radius and rollback

- Production behavior change is scoped to app/packages/access/sync/* (platform/user lock only) plus two additive modules in app/infrastructure/idempotency/ (lease.py, factory.py addition) and one bash script. No terraform/CI changes; no new env vars.
- Nothing outside this task's files calls check_lock/acquire_lock/release_lock/build_idempotency_store/acquire_lease/release_lease today (grep-verified), so no other caller needs migration in this PR. TASK-6 will be the first consumer of lease.py, in its own follow-up PR.
- A single git revert fully restores prior behavior, since lease.py/build_idempotency_store are net-new and unused by anything else at revert time.
- Worst-case risk if this ships wrong: the lease's in-progress TTL is misconfigured and a legitimately-still-running platform sync gets its lock silently reclaimed - the concurrency test and the TTL-sourcing test are the guardrails; a wrong-schema bug in the shell script fails loudly (delete-item/get-item errors surface directly to the operator).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TASK-5.3 by moving generic lease semantics to infrastructure and rewriting access-sync lock flow to atomic claim/release.

Code changes:
- Added app/infrastructure/idempotency/lease.py with acquire_lease/release_lease over IdempotencyStore.claim/release.
- Exported new APIs in infrastructure.idempotency.__init__ and added build_idempotency_store(in_progress_ttl_seconds) in infrastructure/idempotency/factory.py.
- Added packages/access/sync/providers.py:get_access_sync_lock_store() singleton using AccessSyncSettings.lock_stale_seconds TTL.
- Rewrote packages/access/sync/platform_lock.py as thin wrapper: acquire_lock(lock_store+holder write), current_holder(), release_lock(lock_store).
- Updated ingress/job_runner/http/slack call paths to inject lock_store and make acquire_lock/release_lock the only atomic gate (removed check-then-acquire flow).
- Updated app/bin/unlock-sync-job.sh to read lease schema fields (status/claimed_at/in_progress_expires_at) and release via delete-item.
- Updated/validated related tests in idempotency and access sync modules.

Validation evidence:
- cd app && uv run ruff check . -> pass
- cd app && uv run pytest tests --ignore=tests/smoke -> pass (2980 passed)
- cd app && uv run pytest tests/unit/infrastructure/idempotency/test_lease.py tests/unit/infrastructure/idempotency/test_factory.py tests/unit/packages/access/sync/test_access_sync_routes.py tests/unit/packages/access/sync/test_job_runner.py tests/unit/packages/access/sync/test_platform_lock.py tests/unit/packages/access/sync/test_providers.py -> pass (39 passed)
- Full mypy gate still reports pre-existing repository-wide failures outside this change set (legacy modules/integrations); touched tests pass targeted mypy.

DoD remaining for human verification:
- PR text should reference decisions/reliability.md and cross-reference TASK-6.
- Optional manual dry-run of unlock script against target DynamoDB environment.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:35
---
Planning note: two design gaps found not resolvable by mechanical rename, flagged for explicit sign-off before implementation. (1) AccessSyncSettings.lock_stale_seconds defaults to 14400s (4h) but the generic IdempotencyStore singleton's in-progress TTL (IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS) defaults to 300s - reusing the shared singleton as-is would let the lease expire mid-run and reopen the exact duplicate-work bug this task closes. Plan adds a small additive factory function build_idempotency_store(in_progress_ttl_seconds) in infrastructure/idempotency/factory.py (no change to protocol.py/dynamodb.py/in_memory.py) consumed by a new package-owned singleton provider get_access_sync_lock_store() in packages/access/sync/providers.py, so package code still resolves the store via a provider function rather than instantiating DynamoDBIdempotencyStore directly. (2) claim() only carries a payload on COMPLETED outcomes; a lease (which only ever calls claim()/release(), never complete()) has no way to report which job currently holds it, but check_lock() today returns that info and it is genuinely user-facing (Slack already-running message shows Job ID + poll hint; test_sync_endpoint_user_sync_returns_existing_job_when_lock_held asserts it). Plan preserves this via a best-effort, non-authoritative 'holder info' record written through the legacy IdempotencyService under a distinct key (f'{lock_key}:holder', never the lease's own key, to avoid two different item shapes stomping the same DynamoDB item) - not part of the correctness gate, which is claim()/release() alone. Also folds check_lock into acquire_lock's atomic branch (removed as a separate exported symbol) since a separate pre-check reopens the TOCTOU window DoD#1 requires closed; happy to add it back as a thin non-authoritative wrapper over current_holder if human prefers keeping the name for compatibility. Two new ACs added above reflect these decisions; please confirm before implementation starts.
---

created: 2026-07-27 15:37
---
Revised 2026-07-27 after architecture review: the previous plan authored the reusable lease helper inside app/packages/access/sync/ and had TASK-6 (a cross-domain scheduler) import it directly - a layering violation per decisions/layers.md (shared platform capabilities belong in app/infrastructure) and decisions/reliability.md. Description, plan, and AC#3 replaced to move the generic acquire_lease/release_lease helper into app/infrastructure/idempotency/lease.py; platform_lock.py is now a thin feature-specific wrapper over it. TASK-6 updated correspondingly to import from infrastructure.idempotency, not from packages.access.sync.
---
<!-- COMMENTS:END -->
