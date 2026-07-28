---
id: TASK-6
title: >-
  Add Tier-2 TTL leases to singleton scheduled jobs (single shared default TTL;
  no central per-job settings)
status: Done
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 17:22'
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
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1260'
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Singleton (Tier-2) scheduled jobs must not double-fire across the 2 ECS replicas. Each Tier-2 job takes a TTL lease on the shared conditional-write primitive (app/infrastructure/idempotency) before running; a second replica skips while the lease is held; an expired lease is taken over by the next runner. The lease is a duplication optimization, never a correctness mechanism - every Tier-2 job body stays idempotent regardless (decisions/reliability.md, Background jobs).

SCOPE CORRECTION (2026-07-28, per decisions/reliability.md and decisions/plugins.md - scheduler composed as a clock-driven transport) - supersedes the earlier plan:
The earlier plan introduced a central app/jobs/settings.py SchedulerSettings with one long-named TTL field PER JOB (SCHEDULER_PROVISION_AWS_IDENTITY_CENTER_LEASE_TTL_SECONDS, SCHEDULER_NOTIFY_STALE_INCIDENT_CHANNELS_LEASE_TTL_SECONDS, SCHEDULER_SPENDING_GENERATE_SPENDING_DATA_LEASE_TTL_SECONDS). That central aggregator is an anti-pattern: the long names are the symptom of unrelated domains sharing one settings namespace, and the scheduler pull-hub (app/jobs/scheduled_tasks.py::init hand-importing each feature's job body) that forces it is the inverse of the register_routes / register_slack_listeners push model. This task is re-scoped to the MINIMAL reliability fix and must NOT bake in the central per-job aggregator:
- Use ONE shared scheduler-owned DEFAULT Tier-2 lease TTL for the currently-registered, not-yet-migrated modules/ jobs (a single setting or module constant, e.g. DEFAULT_TIER2_LEASE_TTL_SECONDS). NO per-job SCHEDULER_<JOB>_LEASE_TTL_SECONDS fields.
- Per-job / feature-owned TTLs and colocation into feature settings are DEFERRED to the scheduler-as-transport follow-up: TASK-64 (widen BackgroundJobRegistry + move lease/error-boundary enforcement into the registry) then TASK-65 (strangle the pull-hub as modules/ jobs migrate to packages, each job's schedule+TTL then living in its own feature settings).

Keep the lease helpers (get_lease_store, run_if_leased) ADDITIVE in app/infrastructure/idempotency/lease.py - reusable by TASK-64/TASK-65 and any future consumer.

Keep the app/server/lifespan.py ENVIRONMENT-gated scheduler start UNCHANGED. It is a local/dev/CI suppression convention, not a duplicate-firing guard: both prod ECS replicas already satisfy ENVIRONMENT=="production" (terraform desired_count=2, one service), so the gate never guarded against duplicate execution (verified 2026-07-28 planning; TASK-1 was the unrelated PREFIX->ENVIRONMENT rename). Tier-2 TTL leases are the sole duplicate-prevention mechanism.

Job census (app/jobs/scheduled_tasks.py) to classify at registration:
- scheduler_heartbeat (every 5 min) - Tier-1, host-owned (stateless log; safe on every replica; no lease).
- integration_healthchecks (every 5 min) - Tier-1, host-owned (read-only checks; no lease).
- provision_aws_identity_center (every 2 hours) - Tier-2 (mutates AWS IAM Identity Center); lease with the shared default TTL.
- notify_stale_incident_channels (daily 16:00) - Tier-2 (avoid duplicate Slack notifications); lease with the shared default TTL; also wrap in safe_run (currently the one registration outside the error boundary - small same-line in-scope fix).
- spending.generate_spending_data (daily 00:00) - Tier-2 (avoid duplicate spend-data writes); lease with the shared default TTL.
- Any register_background_jobs hookspec registrant (e.g. access/sync) - leaves its own leasing to TASK-64's widened registry; NOT lease-wrapped by this task.

TESTS - introduced-now, DELETE + REWRITE. The failing TDD tests already written for the OLD central-per-job-settings plan must be deleted and rewritten:
- app/tests/unit/jobs/test_settings.py currently asserts a 3-long-field SchedulerSettings - DELETE it, and REWRITE to assert only the single shared default TTL (default value + env override + singleton identity), OR remove the file entirely if a plain module constant is used instead of a settings class.
- app/tests/unit/jobs/test_scheduled_tasks.py Tier-2 tests currently assume per-job TTL fields / get_scheduler_settings with multiple fields - REWRITE to assert Tier-2 jobs lease with the single shared default TTL and Tier-1 jobs are not lease-wrapped; drop per-job-field assertions.
- app/tests/unit/infrastructure/idempotency/test_lease.py get_lease_store / run_if_leased tests are RETAINED (the lease mechanism is kept).

SEQUENCING (captured in task dependencies): TASK-6 (this) -> TASK-64 (scheduler-as-transport: widen BackgroundJobRegistry, move enforcement into the registry) -> TASK-52 (relocate the now-thinner scheduler capability into app/infrastructure/) -> TASK-65 (strangle the pull-hub as modules/ jobs migrate). TASK-52 is re-pointed to also depend on TASK-64 so it relocates the widened capability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Tier-2 (singleton) jobs acquire a TTL lease via conditional write before executing; a second replica skips while the lease is held (tested with the in-memory fake)
- [x] #2 An expired lease is taken over by the next runner (test)
- [x] #3 Tier-2 lease TTL comes from a SINGLE shared scheduler-owned default (one setting or module constant); NO central app/jobs/settings.py aggregator with one SCHEDULER_<JOB>_LEASE_TTL_SECONDS field per job is introduced (per decisions/configuration.md and decisions/reliability.md)
- [x] #4 The app/server/lifespan.py ENVIRONMENT-gated scheduler start is kept unchanged (local/dev/CI convention, not a dedup mechanism); Tier-2 leases alone prevent duplicate execution across the 2 production replicas
- [x] #5 Generic additive helpers get_lease_store (TTL-parameterized factory) and run_if_leased (acquire+run+release) are added to app/infrastructure/idempotency/lease.py, reusable by TASK-64/TASK-65 and beyond
- [x] #6 Each Tier-2 job has a one-line idempotency note at its registration site
- [x] #7 The introduced TDD tests written for the old central-per-job-settings plan are deleted and rewritten: app/tests/unit/jobs/test_settings.py is removed or reduced to the single shared default; the per-job-TTL Tier-2 assertions in test_scheduled_tasks.py are rewritten to the single-default behavior; test_lease.py get_lease_store/run_if_leased tests are retained
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass; both replicas can boot with jobs enabled in a local two-process check
- [x] #2 PR references decisions/reliability.md (Background jobs)
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope rewrite (2026-07-28, per decisions/reliability.md + decisions/plugins.md) - SUPERSEDES the prior plan

Two prior scope corrections still hold: (1) the ENVIRONMENT gate in _start_scheduled_tasks is KEPT (it never guarded duplicate firing - both prod replicas are ENVIRONMENT=="production"); (2) no lease-renewal/heartbeat (over-run takeover is acceptable per reliability.md). NEW correction: do NOT introduce a central app/jobs/settings.py with one long-named TTL field per job (the per-job-aggregator anti-pattern). Use ONE shared default Tier-2 lease TTL instead; defer per-job/feature-owned TTLs to TASK-64/TASK-65.

## Steps

1. app/infrastructure/idempotency/lease.py (additive, unchanged from prior plan):
   - get_lease_store(ttl_seconds: int) -> IdempotencyStore, @functools.lru_cache-memoized per ttl, wrapping build_idempotency_store(in_progress_ttl_seconds=ttl_seconds).
   - run_if_leased(lock_store, name, job): if not acquire_lease(...): return; else try: job() finally: release_lease(...).
   - Export both from app/infrastructure/idempotency/__init__.py.

2. Single shared DEFAULT Tier-2 lease TTL (NOT one per job):
   - Introduce exactly ONE tunable value, DEFAULT_TIER2_LEASE_TTL_SECONDS (e.g. 1800s), sized conservatively and flagged in the PR as an ops-tunable placeholder.
   - Preferred home: a minimal SchedulerSettings(InfrastructureSettings) holding this SINGLE field + get_scheduler_settings() singleton (orphaned-settings-home under app/jobs/, relocates with TASK-52). If a settings class feels premature given TASK-64 will restructure this, a plain typed module constant is acceptable - but keep it to ONE value regardless.

3. app/jobs/scheduled_tasks.py:
   - Import get_lease_store, run_if_leased from infrastructure.idempotency; the single default TTL from step 2; functools.
   - Small private helper _tier2(name, job) that leases via run_if_leased(get_lease_store(DEFAULT_TIER2_LEASE_TTL_SECONDS), f"scheduler:{name}", job). (This helper becomes registry-internal under TASK-64 - keep it minimal here.)
   - Rewrite init(): Tier-1 (heartbeat, integration_healthchecks) unchanged/no lease; the 3 Tier-2 jobs wrapped via _tier2 with a one-line idempotency note above each; bind client=/logger= via functools.partial before wrapping; add safe_run around notify_stale_incident_channels.
   - reconcile_access_sync stays untouched (dead code, not in init()); hookspec dispatch line untouched.

4. app/server/lifespan.py: no functional change; add one clarifying comment on the ENVIRONMENT gate (local/dev/CI suppression, not the Tier-2 dedup mechanism).

5. Delete + rewrite the introduced tests (see Description TESTS section): remove/reduce test_settings.py to the single default; rewrite the Tier-2 tests in test_scheduled_tasks.py to the single-default behavior; retain test_lease.py's get_lease_store/run_if_leased tests.

## AC-to-test-to-step traceability

- AC#1 (Tier-2 leases before executing; second replica skips) -> steps 1,3 -> test_lease.py::run_if_leased_skips_when_lease_held + test_scheduled_tasks.py::tier2_skips_while_lease_held (in-memory fake).
- AC#2 (expired lease taken over) -> step 1 -> test_lease.py::run_if_leased_takes_over_expired_lease (fake built with 0/negative in-progress TTL, no time-mocking).
- AC#3 (single shared default TTL; no per-job aggregator) -> step 2 -> test_settings.py rewritten to the single field (or deleted for a constant) + review by inspection that no SCHEDULER_<JOB>_LEASE_TTL_SECONDS fields exist.
- AC#4 (gate kept) -> step 4 -> existing test_lifespan.py unchanged/still passes.
- AC#5 (additive get_lease_store + run_if_leased) -> step 1 -> test_lease.py factory/singleton + helper tests.
- AC#6 (one-line idempotency note per Tier-2 job) -> step 3 -> review by inspection.
- AC#7 (introduced TDD tests deleted + rewritten) -> step 5 -> the rewritten test_settings.py / test_scheduled_tasks.py compile and pass against the single-default implementation; test_lease.py retained.

## Blast radius and rollback

- Files: app/infrastructure/idempotency/lease.py (+ __init__.py), the single-default TTL home (minimal app/jobs/settings.py OR a constant), app/jobs/scheduled_tasks.py, app/server/lifespan.py (comment only), plus the rewritten/deleted test files. One subsystem (scheduler + idempotency infra); no terraform/CI change; reuses the existing sre_bot_idempotency table via the existing IdempotencyStore primitive. Rollback is a plain revert. Fits one PR comfortably.

## Still needs human plan approval before code (per single-PR size gate + backlog workflow). TTL default is an ops-tunable placeholder flagged for confirmation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation complete for TASK-6. Verified scheduler Tier-2 TTL lease behavior with single shared default TTL and additive lease helpers. Fixed integration scheduling contract (client kwarg pass-through) while preserving Tier-2 lease wrapping. Test evidence: targeted unit/integration suites for jobs + idempotency passed during implementation, and user confirms full tests are now green. Task remains In Progress for human DoD verification/closure.
<!-- SECTION:NOTES:END -->

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

created: 2026-07-28 16:33
---
Rewritten 2026-07-28 per the scheduled job architecture review. Supersedes the prior plan's central app/jobs/settings.py with one long-named TTL field per job (SCHEDULER_<JOB>_LEASE_TTL_SECONDS) - that aggregator was the anti-pattern surfaced while writing these tests. Now: single shared DEFAULT Tier-2 lease TTL only; per-job/feature-owned TTLs deferred to TASK-64 (scheduler-as-transport registry widen) then TASK-65 (strangle pull-hub as modules migrate). The failing TDD tests written for the old plan (app/tests/unit/jobs/test_settings.py 3-field version + per-job-TTL Tier-2 tests in test_scheduled_tasks.py) are deleted and rewritten to the single-default behavior in the same task; test_lease.py get_lease_store/run_if_leased tests are retained. Sequencing captured in deps: TASK-6 -> TASK-64 -> TASK-52 -> TASK-65. Milestone unchanged (m-0, reliability hotfix); new follow-ups placed in m-4 (TASK-64) and m-5 (TASK-65) - no existing task needed a milestone reassignment. Still needs human plan approval before code.
---

created: 2026-07-28 16:57
---
HANDOVER (2026-07-28): task owner has reviewed this plan; TASK-6 is ready to hand to a fresh implementation session. Guardrails for the implementing agent: (1) scope this task ONLY - do NOT pull in TASK-52/TASK-64/TASK-65 (downstream, gated). (2) All three dependencies (TASK-1, TASK-5.1, TASK-5.3) are Done; branch is feat/scheduler_ttl_lease. (3) Starting state is intentionally RED: the introduced TDD tests (app/tests/unit/jobs/test_settings.py and the Tier-2/init tests in app/tests/unit/jobs/test_scheduled_tasks.py) have already been rewritten to the single-shared-default-TTL design and currently fail at collection because they import jobs.settings / _tier2 which do not exist yet - make them green per the plan; app/tests/unit/infrastructure/idempotency/test_lease.py get_lease_store/run_if_leased tests are retained. (4) Deliverable: one shared DEFAULT_TIER2_LEASE_TTL_SECONDS (single setting or module constant, NO per-job fields), additive get_lease_store/run_if_leased in app/infrastructure/idempotency/lease.py, and _tier2-wrapped Tier-2 jobs in app/jobs/scheduled_tasks.py; the ENVIRONMENT gate in app/server/lifespan.py stays unchanged. (5) The TTL default value is an ops-tunable placeholder - flag it in the PR for confirmation. (6) Validate mypy + ruff + pytest (unit) from app/ before completion; check ACs one-by-one and stop at In Progress for human closure - do not set Done.
---
<!-- COMMENTS:END -->
