---
id: TASK-6
title: >-
  Replace the PREFIX-gated scheduler with a Tier-2 TTL lease on the
  conditional-write primitive
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 15:19'
labels:
  - reliability
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
  - TASK-5.1
  - TASK-5.3
references:
  - decisions/reliability.md
  - claude-research-outcome.md
  - 'https://github.com/cds-snc/sre-bot/issues/1260'
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/reliability.md (Background jobs) and claude-research-outcome.md. Today singleton background jobs are prevented from double-firing across the 2 ECS tasks by an environment-shaped gate in _start_scheduled_tasks at app/server/lifespan.py:105 (if app_settings.PREFIX != "") - the not-yet-migrated state.

app/jobs/scheduled_tasks.py registers jobs across unrelated domains (modules.aws.identity_center/spending, modules.incident, integrations.maxmind/opsgenie/google_workspace, packages.access.sync) - the Tier-2 lease is a cross-cutting scheduler capability, not something owned by any one feature package.

Reassessed 2026-07-28 against what TASK-5.1/TASK-5.3/TASK-5.4.1/TASK-5.4.2 actually shipped (all Done): the generic primitive this task needs already exists in full - app/infrastructure/idempotency/lease.py's acquire_lease(lock_store, name)/release_lease(lock_store, name) built on IdempotencyStore.claim/release, plus factory.build_idempotency_store(in_progress_ttl_seconds) for a lease-specific TTL distinct from the generic dedup store's short default. The legacy IdempotencyService/DynamoDBCache/get_idempotency_service stack this task's original research referenced no longer exists at all (deleted in TASK-5.4.2) - nothing legacy remains to import or accidentally reuse.

Firm decisions (supersede the original open questions):
- No lease-renewal/heartbeat capability is needed. decisions/reliability.md is explicit that the lease is a duplication optimization, never a correctness mechanism, and over-run takeover is an accepted outcome given the idempotent-job-body mandate - so a fixed, per-job TTL (sized to that job's own expected max run duration) is sufficient, mirroring the sizing choice already made for the Access Sync platform/user lock (TASK-5.3, lock_stale_seconds=14400).
- Do not reuse the generic get_idempotency_store() singleton's IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS (300s) default for any Tier-2 job lease without checking fit; call build_idempotency_store(ttl_seconds=...) with a TTL sized to each job (or job class).
- If any Tier-2 job needs "who currently holds this" reporting for operator/observability purposes, that is a distinct, best-effort keyed-record capability (own small store over infrastructure.storage.StorageService, mirroring Access Sync's JobStatusStore) - never folded into the lease's own claim()/release() correctness gate, and never the deleted legacy idempotency cache.

Boilerplate-reduction addition in scope for this task (since it is the first consumer needing several differently-tiered leases across many unrelated jobs): add two small, generic, additive helpers to app/infrastructure/idempotency/lease.py (not scheduler-specific, reusable by any future consumer) -
(a) a TTL-parameterized singleton factory (e.g. get_lease_store(ttl_seconds: int) -> IdempotencyStore, functools.lru_cache-memoized per ttl_seconds value) wrapping build_idempotency_store, so callers stop hand-rolling their own per-TTL module-level singleton cache (Access Sync's providers.py currently does this ad hoc for one fixed TTL);
(b) an acquire+run+release convenience wrapper (e.g. run_if_leased(lock_store: IdempotencyStore, name: str, job: Callable[[], None]) -> None, or an equivalent context manager) that collapses the acquire-lease/skip-if-not-acquired/finally-release sequence into one call, so each Tier-2 job registration site needs about one line, not a hand-rolled try/finally.

Job census (app/jobs/scheduled_tasks.py, confirmed 2026-07-28) to classify at registration:
- scheduler_heartbeat (every 5 min) - Tier-1 (stateless log line, safe on every replica).
- integration_healthchecks (every 5 min) - Tier-1 (read-only checks, safe on every replica).
- provision_aws_identity_center (every 2 hours) - Tier-2 (mutates AWS IAM Identity Center state).
- notify_stale_incident_channels (daily 16:00) - Tier-2 (avoid duplicate Slack notifications).
- spending.generate_spending_data (daily 00:00) - Tier-2 (avoid duplicate data generation/writes).
- Any job registered via the register_background_jobs hookspec (_ScheduleBackgroundJobRegistry.register, e.g. Access Sync's coordinator job via get_access_sync_coordinator) - classify at its own registration site, each registrant owns its Tier-1/Tier-2 call and its own lease TTL if Tier-2.

Ordering note: TASK-52 (relocate the app/jobs scheduler registry into app/infrastructure) depends on this task and stays To Do until this one ships - implement in place under app/jobs/ as it exists today; if a shared default lease-TTL setting is needed, add it under app/jobs/ now (an orphaned-settings-home instance, same incremental-migration precedent TASK-5.1 used) rather than waiting on TASK-52 to relocate it first.

Steps:
1. Consume acquire_lease/release_lease (and the two new additive helpers above) directly from app/infrastructure/idempotency/lease.py. Do not import from app/packages/access/sync/ - that package's platform_lock.py is a feature-specific wrapper over the same shared helper, not the helper itself.
2. Classify each registered job Tier-1 (safe to run on every replica - runs everywhere, no lease) or Tier-2 (singleton - takes the lease before each run, with a TTL sized to its own expected max duration).
3. The lease is a duplication optimization, never a correctness mechanism: each Tier-2 job body must be idempotent regardless (document per job).
4. Delete the PREFIX/environment gate in app/server/lifespan.py; keep desired_count=2 for HA.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tier-2 jobs acquire a TTL lease via conditional write before executing, using a TTL sized to that job's own expected max duration (not the generic 300s dedup default); a second replica skips while the lease is held (test with the in-memory fake)
- [ ] #2 An expired lease is taken over by the next runner (test)
- [ ] #3 The app/server/lifespan.py ENVIRONMENT-gated scheduler start is kept unchanged (local/dev/CI safety convention, not a dedup mechanism); Tier-2 leases alone prevent duplicate execution across the 2 production replicas
- [ ] #4 Each Tier-2 job has a one-line idempotency note at its registration site
- [ ] #5 A generic, TTL-parameterized lease-store singleton factory and an acquire+run+release convenience helper are added to app/infrastructure/idempotency/lease.py (additive, reusable by any future consumer beyond the scheduler)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; both replicas can boot with jobs enabled in a local two-process check
- [ ] #2 PR references decisions/reliability.md (Background jobs)
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope adjustment (from 2026-07-28 planning session, human-confirmed)

AC#3 as originally written ("delete the PREFIX/environment gate") is WRONG and is dropped.
Research: `app_settings.ENVIRONMENT != "production"` in `_start_scheduled_tasks`
(app/server/lifespan.py) is NOT a duplicate-firing guard - both production ECS
replicas already satisfy `ENVIRONMENT == "production"` (terraform desired_count=2,
one service, no separate staging service), so it never prevented Tier-2 double-firing
and doesn't need to change to fix it. It is the same established, pervasive
`ENVIRONMENT`-gating convention used at 12+ other call sites app-wide, and is exactly
the "legitimate environment-conditional behavior (...prod-only side effects)" case the
`settings-singleton` skill sanctions. Deleting it would newly start the scheduler
(real AWS/Slack calls) on every local dev run and in CI - an unrelated, larger
behavior change with no decisions/ mandate. Decision (human-confirmed): **keep the
gate unchanged**; Tier-2 leases are the sole duplicate-prevention mechanism.

## Steps

1. `app/infrastructure/idempotency/lease.py`: add two additive helpers (no change to
   existing `acquire_lease`/`release_lease`):
   - `get_lease_store(ttl_seconds: int) -> IdempotencyStore`, `@functools.lru_cache`-
     memoized per distinct `ttl_seconds`, calling `build_idempotency_store(
     in_progress_ttl_seconds=ttl_seconds)`. Generalizes the ad hoc pattern
     `packages/access/sync/providers.py::get_access_sync_lock_store()` already
     hand-rolls for one fixed TTL.
   - `run_if_leased(lock_store: IdempotencyStore, name: str, job: Callable[[], None])
     -> None`: `if not acquire_lease(lock_store, name): return`; else
     `try: job() finally: release_lease(lock_store, name)`.
   - Export both from `app/infrastructure/idempotency/__init__.py` (`__all__` +
     import line, next to the existing `acquire_lease`/`release_lease` export).

2. `app/jobs/settings.py` (new file): `SchedulerSettings(InfrastructureSettings)`
   (orphaned-settings-home instance under app/jobs/, precedent: TASK-5.1; relocates
   with the rest of app/jobs/ under TASK-52) with one TTL field per Tier-2 job in
   this file's scope, each a clearly-flagged placeholder pending ops sign-off:
   - `SCHEDULER_PROVISION_AWS_IDENTITY_CENTER_LEASE_TTL_SECONDS: int = 1800`
   - `SCHEDULER_NOTIFY_STALE_INCIDENT_CHANNELS_LEASE_TTL_SECONDS: int = 600`
   - `SCHEDULER_SPENDING_GENERATE_SPENDING_DATA_LEASE_TTL_SECONDS: int = 1800`
   Plus `get_scheduler_settings()` singleton provider (`@lru_cache(maxsize=1)`),
   mirroring `infrastructure/idempotency/settings.py::get_idempotency_settings`.

3. `app/jobs/scheduled_tasks.py`:
   - Import `get_lease_store`, `run_if_leased` from `infrastructure.idempotency`;
     `get_scheduler_settings` from `jobs.settings`; add `import functools`.
   - Add a private helper:
     ```python
     def _tier2(job_name: str, ttl_seconds: int, job: Callable[[], None]) -> Callable[[], None]:
         """Wrap a Tier-2 job so only the lease holder executes it.

         The lease is a duplication optimization, not a correctness mechanism -
         `job` must remain idempotent regardless (decisions/reliability.md).
         """
         lease_store = get_lease_store(ttl_seconds)

         def wrapper() -> None:
             run_if_leased(lease_store, job_name, job)

         return wrapper
     ```
   - Rewrite `init()` classifying every locally-registered job:
     - Tier-1 (unchanged, no lease): `scheduler_heartbeat`, `integration_healthchecks`.
     - Tier-2 (leased, one-line idempotency note above each registration):
       - `provision_aws_identity_center` - mutates AWS IAM Identity Center
         membership; lease TTL 1800s (job runs every 2h).
       - `notify_stale_incident_channels` (imported from
         `modules.incident.notify_stale_incident_channels`) - avoids duplicate
         Slack notifications; bind `client=bot.client` via `functools.partial`
         before wrapping (also newly wrapped in `safe_run`, matching every other
         job - it was the one registration not already inside the error
         boundary; small, same-line, in-scope fix, not new scope).
       - `spending.generate_spending_data` - avoids duplicate spend-data
         writes; bind `logger=logger` via `functools.partial` before wrapping.
     - Each registration becomes: fetch the job's TTL off `get_scheduler_settings()`,
       call `schedule...do(safe_run(_tier2(name, ttl, job)))`. Lease keys:
       `"scheduler:provision_aws_identity_center"`,
       `"scheduler:notify_stale_incident_channels"`,
       `"scheduler:spending_generate_spending_data"`.
   - No change to `reconcile_access_sync` (dead code today - not wired into
     `init()`/schedule - leave as is, out of this task's job census) or to the
     hookspec dispatch line (`register_background_jobs`) - hookspec registrants
     (e.g. Access Sync's own reconciliation job) classify and lease themselves at
     their own registration site per the task's job census note; not touched here.

4. `app/server/lifespan.py`: no functional change (see scope adjustment above).
   Add one clarifying inline comment on the `ENVIRONMENT != "production"` check
   noting it is a local/dev/CI suppression switch, not the Tier-2 dedup mechanism,
   to prevent this exact misreading from recurring.

## AC-to-step-to-test traceability

- AC#1 (Tier-2 jobs lease before executing; second replica skips) -> step 3
  (`_tier2`/`run_if_leased`) -> `test_lease.py::test_run_if_leased_skips_when_lease_held`
  and `test_scheduled_tasks.py::test_tier2_skips_second_call_while_lease_held`.
- AC#2 (expired lease taken over) -> step 1 (`run_if_leased` reuses
  `acquire_lease`'s existing expiry-aware `claim()`) ->
  `test_lease.py::test_run_if_leased_takes_over_expired_lease` (build the fake
  store with a negative/zero TTL so `expires_at < now` deterministically, no
  time-mocking needed, mirrors existing `test_lease.py` style).
- AC#3 (rewritten - gate retained, not relied on for dedup) -> step 4 -> no new
  test; existing `test_lifespan.py` gate tests are unchanged/still pass.
- AC#4 (one-line idempotency note per Tier-2 job) -> step 3 registration comments
  -> reviewed by inspection (comments are not independently testable).
- AC#5 (generic TTL-parameterized factory + acquire+run+release helper, additive)
  -> step 1 -> `test_lease.py::test_get_lease_store_returns_singleton_per_ttl` /
  `test_get_lease_store_returns_distinct_instance_for_different_ttl`.

## Test matrix

- `app/tests/unit/infrastructure/idempotency/test_lease.py` (extend):
  - `get_lease_store(ttl)` called twice with the same ttl returns the same
    instance (`is`); called with a different ttl returns a different instance.
    Teardown: `get_lease_store.cache_clear()`.
  - `run_if_leased` executes `job` and releases the lease when acquired.
  - `run_if_leased` does not execute `job` when the lease is already held.
  - `run_if_leased` releases the lease even when `job` raises (exception still
    propagates to the caller - `safe_run` remains the layer that swallows it).
  - `run_if_leased` takes over an expired lease and executes `job`.
- `app/tests/unit/jobs/test_scheduled_tasks.py` (extend): patch
  `jobs.scheduled_tasks.get_lease_store` to return a shared
  `InMemoryIdempotencyStore` fixture; test `_tier2(...)()`:
  - first invocation runs the wrapped job.
  - a second invocation while the first's lease is still held skips the job
    (in-memory fake, per AC#1).
  - an invocation after the lease has expired (fake built with a negative TTL)
    re-runs the job (per AC#2).
  - `init()` registers exactly the 4 locally-owned jobs (2 Tier-1 direct
    `safe_run`, 2 Tier-2 via `_tier2`) plus dispatches
    `register_background_jobs` once; Tier-1 jobs are not lease-wrapped.
- `app/tests/unit/jobs/test_settings.py` (new): `SchedulerSettings` defaults;
  env var overrides each TTL field; `get_scheduler_settings()` singleton identity.
- `app/tests/integration/server/test_lifespan.py`: unchanged, must still pass
  as-is (proves the gate truly wasn't touched).

## Assumptions / doubts requiring verification before or during review

1. TTL defaults (1800s for identity-center provisioning and spending generation,
   600s for the incident notifier) are placeholder estimates sized only from each
   job's schedule interval, not measured run duration - flag explicitly in the PR
   description for an operator with real run-time data to confirm or adjust before
   merge (same provisional-placeholder pattern used in TASK-5.2/TASK-5.3).
2. `notify_stale_incident_channels`'s registration site is not currently wrapped in
   `safe_run` - step 3 fixes this as an in-scope, same-line correction consistent
   with decisions/reliability.md's error-boundary requirement; flagged here in case
   a reviewer considers it out of this task's stated scope.
3. `reconcile_access_sync` in `scheduled_tasks.py` is dead code (defined, never
   registered in `init()`) - left untouched; out of this task's job census.

## Blast radius and rollback

- Files touched: `app/infrastructure/idempotency/lease.py`,
  `app/infrastructure/idempotency/__init__.py`, `app/jobs/settings.py` (new),
  `app/jobs/scheduled_tasks.py`, `app/server/lifespan.py` (comment only), plus
  the four test files above. One subsystem (scheduler + idempotency
  infrastructure), no terraform/CI changes, no settings renames. Single-PR size
  gate: fits comfortably (~5 production files, well under 400 LOC).
- Runtime blast radius: changes `init()`'s job registration and adds a lease
  check before 3 existing Tier-2 job bodies; job bodies themselves are
  unchanged. Rollback is a plain revert - no data migration, no schema change
  (reuses the existing `sre_bot_idempotency` table via the existing
  `IdempotencyStore` primitive).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 17:58
---
TASK-5 was decomposed on 2026-07-24 (single-PR size gate) into TASK-5.1..TASK-5.4; see TASK-5 for the full rationale. This task's dependency has been re-pointed from TASK-5 directly onto TASK-5.1 (the IdempotencyStore claim/complete/release primitive this Tier-2 lease is built on) and TASK-5.3 (the Access Sync platform/user lock rewrite, which produces a lease helper on the same primitive). Consume TASK-5.3's lease helper for the Tier-2 job lease here rather than reimplementing a second lease on top of TASK-5.1 directly - avoid two competing lease implementations on the same conditional-write primitive.
---

created: 2026-07-27 15:39
---
Correction 2026-07-27: TASK-5.3's plan was revised after architecture review - the reusable lease helper is now app/infrastructure/idempotency/lease.py (acquire_lease/release_lease), not code inside app/packages/access/sync/. Description updated so this task's Tier-2 lease imports that infra module directly; the dependency on TASK-5.3 is kept only because TASK-5.3's PR is what delivers lease.py, not because this task should import anything from the access/sync package.
---

created: 2026-07-28 12:45
---
Reassessed 2026-07-28 (architecture mode) now that TASK-5.1/TASK-5.3/TASK-5.4.1/TASK-5.4.2 are all Done. The generic lease primitive this task needs already ships in app/infrastructure/idempotency/lease.py (acquire_lease/release_lease) plus factory.build_idempotency_store(ttl_seconds) for a lease-specific TTL — no further infra primitive work is required before this task can start, only two small additive ergonomics helpers (a TTL-parameterized singleton factory and an acquire+run+release convenience wrapper) scoped into this task's own steps since it is the first consumer needing several differently-tiered leases. Firmly decided: no lease-renewal/heartbeat capability (over-run takeover is an accepted, non-correctness-breaking outcome per decisions/reliability.md); each Tier-2 job's TTL must be sized to its own expected max duration rather than reusing the generic dedup store's 300s default. Holder/status reporting, if ever needed for a Tier-2 job, is a separate keyed-record capability over infrastructure.storage.StorageService (mirroring Access Sync's JobStatusStore) — never the lease's own correctness gate, and never the now-fully-deleted legacy IdempotencyService. decisions/reliability.md's Background jobs paragraph was updated in the same pass to document this shipped-primitive location and the no-renewal/per-job-TTL decision for future readers. Dependencies (TASK-1, TASK-5.1, TASK-5.3) are all Done, so TASK-6 is now unblocked; still requires its own human-approved implementation plan (--plan) before any code, per the single-PR size gate — not written in this pass.
---

created: 2026-07-28 15:19
---
Plan written 2026-07-28 (task-planner). Scope adjustment confirmed with human: AC#3 was wrong as originally written ("delete the PREFIX/environment gate"). The ENVIRONMENT != "production" check in _start_scheduled_tasks (app/server/lifespan.py) is NOT what prevents Tier-2 double-firing - both prod ECS replicas already satisfy ENVIRONMENT=="production" (desired_count=2, one service), so the gate never guarded against duplicate execution. It is the same established, pervasive ENVIRONMENT-gating convention used at 12+ other call sites app-wide (dev-bypass, notify client, webhooks, logging) to suppress side-effecting behavior outside production - exactly the settings-singleton skill's sanctioned "legitimate environment-conditional behavior (prod-only side effects)" case. Deleting it would newly start the real scheduler (AWS/Slack calls) on every local dev run and in CI, an unrelated and larger behavior change with no decisions/ mandate. Decision: the gate is KEPT unchanged; AC#3 rewritten to say so; Tier-2 TTL leases (this task's actual deliverable) are the sole duplicate-prevention mechanism. Full implementation plan (steps, AC-to-test traceability, test matrix, TTL-default assumptions flagged for ops sign-off, blast radius/rollback) written via --plan. Confirmed single-PR size: ~5 production files (infrastructure/idempotency/lease.py + __init__.py, new app/jobs/settings.py, app/jobs/scheduled_tasks.py, one-comment-only app/server/lifespan.py), well under the size gate - no decomposition needed. Ready for human plan review before implementation.
---
<!-- COMMENTS:END -->
