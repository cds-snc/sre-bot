---
id: TASK-6
title: >-
  Replace the PREFIX-gated scheduler with a Tier-2 TTL lease on the
  conditional-write primitive
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 12:45'
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
- [ ] #3 The scheduler-gating conditional on PREFIX/environment in app/server/lifespan.py is deleted
- [ ] #4 Each Tier-2 job has a one-line idempotency note at its registration site
- [ ] #5 A generic, TTL-parameterized lease-store singleton factory and an acquire+run+release convenience helper are added to app/infrastructure/idempotency/lease.py (additive, reusable by any future consumer beyond the scheduler)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; both replicas can boot with jobs enabled in a local two-process check
- [ ] #2 PR references decisions/reliability.md (Background jobs)
<!-- DOD:END -->

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
<!-- COMMENTS:END -->
