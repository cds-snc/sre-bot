---
id: TASK-64
title: >-
  Widen BackgroundJobRegistry and move lease/error-boundary enforcement into the
  scheduler registry (scheduler-as-clock-driven transport)
status: To Do
assignee: []
created_date: 2026-07-28 16:29
updated_date: '2026-11-18T19:35:00Z'
labels:
  - architecture
  - reliability
  - layers
milestone: m-4
dependencies: []
references:
  - decisions/reliability.md
  - decisions/plugins.md
  - decisions/platform-transports.md
  - https://github.com/cds-snc/sre-bot/issues/1373
priority: medium
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/reliability.md (Background jobs) + decisions/plugins.md + decisions/platform-transports.md. The scheduler is a clock-driven host capability that should be composed like a transport: the host owns the runtime and features push their own jobs at startup via the register_background_jobs hookspec, exactly as features push routers via register_routes.

Current gap: app/jobs/models.py BackgroundJobRegistry.register(*, job_name, schedule, job) is too narrow to be that push boundary - it accepts a daily .at() string only (no interval expression, no Tier classification, no lease TTL). Because the Protocol cannot express interval jobs (every N minutes/hours) or singleton leasing declaratively, the timing plumbing, the safe_run error boundary, and the Tier-2 lease (_tier2 from TASK-6) are all hand-wired centrally in app/jobs/scheduled_tasks.py::init instead of being applied by the registry. That is why access/sync (the one correct register_background_jobs consumer today) can only register a plain daily job and cannot declare a Tier-2 lease through the boundary.

Scope: widen the registry Protocol and make the scheduler registry adapter (the host-owned runtime) apply the plumbing, so a registration site declares intent only.
- Widen BackgroundJobRegistry.register to carry: (a) a schedule expression rich enough for both interval (every N minutes/hours) and daily-at; (b) Tier classification (Tier-1 run-everywhere vs Tier-2 singleton); (c) optional lease_ttl_seconds for Tier-2. Value types / Protocols only - cross-platform hookspec purity per plugins.md.
- Move safe_run (error boundary) and run_if_leased (Tier-2 lease, from TASK-6's lease.py helpers) enforcement INTO the registry adapter. After this, TASK-6's central _tier2 wrapper in scheduled_tasks.py is deleted and its behavior lives in the adapter; each registration (host-owned or feature hookimpl) supplies tier + ttl + schedule, never a hand-rolled try/finally.
- The two host-owned jobs (scheduler_heartbeat, integration_healthchecks) register as Tier-1 through the same widened path.
- The single shared default lease TTL from TASK-6 stays for now (removed later by TASK-B when the last modules/ job is strangled); this task does NOT yet colocate per-job TTLs into feature settings - that is TASK-B, gated on the modules->packages migration.

Sequencing: TASK-6 (in-place Tier-2 lease, single default TTL) -> THIS TASK (widen the registry + move enforcement into it, in place under app/jobs/) -> TASK-52 (relocate the now-thinner capability into app/infrastructure/) -> TASK-B (strangle the pull-hub as modules/ jobs migrate). TASK-52 is re-pointed to depend on this task so it relocates the widened capability rather than the narrow one.

This task needs its own human-approved implementation plan (backlog task edit <id> --plan) via the task-planner workflow before any code, per the single-PR size gate.

BREAKDOWN GUIDANCE FOR THE PLANNING CODING AGENT: check the single-PR size gate. Widening the Protocol + rewriting the schedule-library adapter + migrating all existing registration sites (2 host Tier-1, 3 modules Tier-2, 1 access/sync hookimpl) plus updating tests may exceed ~400 LOC / one reviewable PR. If so, decompose into safe incremental subtasks, e.g.: (1) widen the Protocol + adapter with a back-compatible shim and migrate the host-owned Tier-1 jobs; (2) migrate the 3 Tier-2 modules jobs onto the widened path and delete _tier2; (3) migrate the access/sync hookimpl to declare its Tier/TTL through the boundary. Keep the schedule-library-adapter rewrite (mechanical) separate from any behavior change where possible (copilot-instructions: do not mix refactor + behavior in one PR).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 BackgroundJobRegistry.register_interval and register_daily are the widened Protocol (TASK-145.5.7.1): schedule as value types (an interval timedelta, a daily HH:MM UTC), Tier as lease_ttl (None = Tier-1 on every replica, a value = Tier-2 under a lease of that TTL); their docstrings and decisions/reliability.md state when a job first runs (an interval job one interval after registration, a daily job at the next HH:MM UTC)
- [x] #2 The scheduler registry adapter applies the safe_run error boundary and Tier-2 lease enforcement (run_if_leased) centrally; every registration site (host-owned or feature hookimpl) declares tier + ttl + schedule and contains no hand-rolled try/finally or _tier2 wrapper
- [x] #3 TASK-6's central _tier2 wrapper in scheduled_tasks.py is deleted; its behavior now lives in the registry adapter
- [x] #4 The two host-owned jobs (scheduler_heartbeat, integration_healthchecks) register as Tier-1 through the widened path; existing Tier-2 jobs are migrated onto it with no behavior change (tests)
- [x] #5 The single shared default lease TTL from TASK-6 is retained (removed later by TASK-B); this task does NOT colocate per-job TTLs into feature settings
- [ ] #6 A Tier-2 lease is held for a minimum time (just under the interval for an interval job, a fixed hold for a daily job; decisions/reliability.md, 2026-11-18): a run that ends before that time keeps the lease until its start plus the minimum hold, through a conditional update under its claim token, never a delete; the TTL stays the maximum hold. A test runs a short job on two simulated replicas whose ticks are about a second apart and asserts a single run per tick.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass (behavior unchanged for existing jobs; new Protocol shape covered)
- [ ] #2 A human-approved implementation plan exists on this task (via task-planner) before any implementation PR opens; planner has checked the single-PR size gate and decomposed if needed
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-18 against main 98918309 (row 18f, doc-11). Revised the same day after the program-scope OQ assessment (comment on this task): two PRs from main, refactor first (CLAUDE.md size gate: no mechanical refactor mixed with a behavior change): TASK-64.1 registrations through the registry (row 18f.1, branch task-64.1-registry-registrations), then TASK-64.2 the minimum hold (row 18f.2, branch task-64.2-lease-minimum-hold). This parent holds the shared research; each subtask gets its own plan on approval.

## Where the task stands on main

- AC #1 (shape) mostly landed with TASK-145.5.7.1 (2026-11-04, human-approved): contracts/scheduler/registry.py BackgroundJobRegistry has register_interval(every: timedelta) and register_daily(schedule: "HH:MM") with lease_ttl: timedelta | None (None = Tier-1, a value = Tier-2). What is missing is the first-run timing statement (TASK-145.5.7.3 note; reliability.md:32 "the widened schedule expression (TASK-64) states it").
- AC #2: the registry adapter jobs/scheduled_tasks.py:32-104 already applies safe_run and run_if_leased for feature jobs. The legacy pull-hub registrations bypass it: init() at jobs/scheduled_tasks.py:147-163 calls schedule.every(...) directly and wraps three jobs in _tier2 (:126-134).
- AC #6 is new: infrastructure/coordination/lease.py:9-17 run_if_leased releases (deletes) at job end, so a short run on one replica lets the second replica run the same tick (two reports per interval from the upgrade dry run, 2026-11-17).

Registration sites (call sites):
- jobs/scheduled_tasks.py:147 scheduler_heartbeat, every 5 min, Tier-1 (host)
- jobs/scheduled_tasks.py:148 integration_healthchecks, every 5 min, Tier-1 (host)
- jobs/scheduled_tasks.py:151 provision_aws_identity_center, every 2 h, _tier2 lease scheduler:provision_aws_identity_center, default TTL 1800 s
- jobs/scheduled_tasks.py:155 notify_stale_incident_channels_job, daily 16:00, _tier2 scheduler:notify_stale_incident_channels, gated on the Slack tenant
- jobs/scheduled_tasks.py:161 spending.execute_spending_data_update_job, daily 00:00, _tier2 scheduler:spending_generate_spending_data
- features/incident/response/plugin.py:106 incident_legacy_upgrade, interval upgrade_interval_minutes (30), lease_ttl upgrade_lease_ttl_seconds (900)
- packages/access/sync/__init__.py:91 access_sync_reconciliation, daily, Tier-1 (its own platform lock inside)
- packages/oncall_sync/__init__.py:48 oncall_sync, every 5 min, Tier-1
Lease consumers outside the scheduler: packages/access/sync/providers.py:29 build_lease_store (platform lock; its release semantics stay unchanged).
ConditionalWriteStore implementations: infrastructure/coordination/dynamodb.py, infrastructure/coordination/in_memory.py (conformance suite tests/integration/infrastructure/coordination/ enrols both; the enrollment test fails if one is missed). Test-only Protocol doubles: tests/unit/contracts/coordination/conftest.py:31, test_coordination_store_protocol.py:47.
IAM: terraform/iam.tf:34-48 already grants dynamodb:UpdateItem on local.dynamodb_table_arns (the coordination table included): no terraform change, so deploy-checks are not required.

## Design

Minimum hold (ShedLock lockAtLeastFor / lockAtMostFor; reliability.md:32 and the 2026-11-18 Changes line):
- hold = min(lease TTL, interval - margin). Daily: interval is one day, so hold = TTL, the "fixed hold" for a daily job. The TTL stays the maximum hold (ADR) and is never exceeded (OQ2).
- margin: [scheduler] lease_hold_margin_seconds, typed setting, default 5 (covers the store's whole-second expiry, the 1 s schedule poll and replica clock skew). A replica's next tick of the same job is at least one interval after its previous start (the schedule library schedules the next run from the end of the last), so the hold never blocks the holder's own next tick.
- run_if_leased(lease_store, name, job, *, min_hold: timedelta | None = None): records start before acquire; after the job (in finally, so a failed run holds too, as ShedLock does) it calls lease_store.release(name, token, not_before=start + min_hold). When the end is already past not_before, release deletes as today.
- LeaseStore.release(name, claim_token, *, not_before: float | None = None) -> bool: None or a past instant deletes (today); a future instant calls the primitive's expire_at. False, changing nothing, when the token no longer holds the lease (unchanged ownership rule).
- New primitive method ConditionalWriteStore.expire_at(key, claim_token, at: int) -> bool: sets an in-progress claim held by claim_token to expire at epoch second `at` (in_progress_expires_at and ttl), never a delete. False, writing nothing, when the token does not hold the key in progress or the key is COMPLETED. DynamoDB: UpdateItem, ConditionExpression "#claim_token = :claim_token AND #status = :in_progress", ConditionalCheckFailedException -> False with claim_ownership_lost warning (operation="expire_at"), other errors -> RuntimeError (as release). In-memory: same under the lock. Tests move time with freezegun (decisions/testing.md:30), no clock parameter.
- IdempotencyStore does not expose it (dedup has no use for it; OQ3).

Registry and legacy jobs (AC #2-#5):
- _ScheduleBackgroundJobRegistry computes the hold at registration and passes it to run_if_leased; the registration debug event gains lease_min_hold_seconds.
- init() registers the two host jobs through registry.register_interval (Tier-1) and the three legacy Tier-2 jobs through register_interval / register_daily with lease_ttl=timedelta(seconds=default_tier2_lease_ttl_seconds) and job_name provision_aws_identity_center, notify_stale_incident_channels, spending_generate_spending_data, so the lease keys (scheduler:<job_name>) are unchanged. The Slack tenant gate stays in init(). _tier2 deleted. The registry is built before the host jobs instead of after.
- Registry docstrings state first-run timing: an interval job first runs one interval after registration (every deploy restarts the count); a daily job at the next HH:MM UTC. No first_run parameter (no job needs another start; OQ4).

## Slices (approved split)

- TASK-64.1 (pure refactor, no behavior change): init() registers the two host Tier-1 jobs and the three legacy Tier-2 jobs through the registry (same schedules, same safe_run, lease names scheduler:<job_name> unchanged, TTL default_tier2_lease_ttl_seconds); _tier2 deleted; registry docstrings and reliability.md state first-run timing; AC #1 (reworded), #2, #3, #4, #5. Steps 7 (registrations part), 8, 9 (timing sentence). ~60 prod lines, 2 files plus reliability.md.
- TASK-64.2 (behavior): the minimum hold on every Tier-2 job at once: steps 1-6, 7 (hold part), 9 (hold rule, Checks, Changes); AC #6. ~110 prod lines, 8 files plus base.toml and reliability.md. TASK-145.9.2 and TASK-147.6 depend on it.

## Steps (TDD: each test first, red, then the code)

1. contracts/coordination/store.py: expire_at on the Protocol with the docstring above. Test doubles at tests/unit/contracts/coordination/conftest.py and test_coordination_store_protocol.py gain the method.
2. Conformance (tests/integration/infrastructure/coordination/test_coordination_store_conformance.py, both stores): holder's expire_at returns True and keeps the key IN_PROGRESS until `at`, so a second claim before `at` is IN_PROGRESS and after `at` is NEW; stale token returns False and leaves the new holder's record; COMPLETED key returns False and stays COMPLETED; missing key returns False.
3. infrastructure/coordination/dynamodb.py and in_memory.py: expire_at.
4. contracts/coordination/lease.py: release(..., not_before=). Tests in tests/unit/contracts/coordination/test_coordination_lease_store.py: not_before None deletes; future keeps the lease (acquire by another caller fails) until it passes; past deletes; stale token False.
5. infrastructure/coordination/lease.py: run_if_leased min_hold. Tests in tests/unit/infrastructure/coordination/test_coordination_run_if_leased.py: no min_hold releases at end (unchanged); a run shorter than min_hold keeps the lease until start + min_hold; a run longer than min_hold releases at end; a failing job still holds and re-raises.
6. jobs/settings.py: lease_hold_margin_seconds (int, >= 0, default 5), declared in config/base.toml [scheduler] (configuration.md:37: the base file holds every default). tests/unit/jobs/test_jobs_scheduler_settings_files.py covers the default.
7. jobs/scheduled_tasks.py: hold computation, init() through the registry, _tier2 deleted. Tests:
   - tests/unit/jobs/test_jobs_scheduled_tasks_registry_lease.py: hold = interval - margin when below the TTL; hold = TTL for a daily job and when the TTL is shorter than the interval; Tier-1 takes no lease (unchanged).
   - New tests/unit/jobs/test_jobs_scheduler_lease_minimum_hold.py (AC #6): two registries (two simulated replicas) over one in-memory store, time moved with freezegun; each tick runs replica A then replica B about a second later; a job of 0.1 s runs once per tick across three ticks; a control with run_if_leased called without min_hold runs twice per tick, showing the regression the hold closes.
   - tests/unit/jobs/test_scheduled_tasks.py: init() registers heartbeat and health checks as Tier-1 interval jobs, the three legacy jobs as Tier-2 with the default TTL and their unchanged lease names, the nudge only with a Slack tenant; no schedule.every call outside the registry.
8. contracts/scheduler/registry.py: docstrings (first-run timing, minimum hold).
9. decisions/reliability.md Background jobs: replace "When a job first runs is the scheduler library's default today ... TASK-64 states it" with the stated timing; the hold rule's numbers (min(TTL, interval - margin), a failed run holds, a run past its hold releases at end); expire_at named beside acquire/release; legacy pull-hub registrations go through the registry. Checks line: a run shorter than its hold leaves the lease held until start plus the hold, on both stores. Changes line dated 2026-11-18 (TASK-64).
10. Notes: TASK-148 (expire_at stays when the duration moves onto claim), TASK-127 (integration_healthchecks now registers through the registry; its fate is still 127's), TASK-52 (moves the thinner runtime), TASK-145.9.2 and TASK-147.6 (register with lease_ttl; the hold applies automatically).

## AC traceability

- AC #1 -> step 8 (shape exists; timing stated) -> registry tests, docstrings
- AC #2 -> step 7 -> test_scheduled_tasks.py (no direct schedule.every), registry lease tests
- AC #3 -> step 7 -> _tier2 gone (test_scheduled_tasks.py; rg)
- AC #4 -> step 7 -> test_scheduled_tasks.py; legacy_surface job-run pins (test_aws_identity_center_provision_job_run.py, test_incident_stale_channel_job_run.py) stay green
- AC #5 -> step 7 -> legacy Tier-2 TTL = default_tier2_lease_ttl_seconds (test)
- AC #6 -> steps 1-7 -> conformance, lease facade, run_if_leased, test_jobs_scheduler_lease_minimum_hold.py
- DoD #1 -> full gates at the end

## Size

~150 production lines (contract 15, facade 15, dynamodb 35, in-memory 20, run_if_leased 20, registry and init 35 net, settings 5, docstrings) over 8 production files plus reliability.md; two subsystems (coordination, scheduler). Under the gate. The legacy registrations moving onto the registry are not a pure refactor: each Tier-2 job gains the hold through the move (OQ1).

## Effect in production after merge

- Incident legacy upgrade (interval 30 min, TTL 900 s): hold 900 s; the second replica's tick 0.7 s later is skipped, so one report per interval.
- provision_aws_identity_center (2 h, TTL 1800): hold 1800 s. Stale nudge and spending (daily, TTL 1800): hold 1800 s.
- A lease now outlives a short run, so a deploy within the hold after a run does not rerun the job until the hold passes (at most one TTL); every body is idempotent.

## Blast radius and rollback

Merging deploys. Wrong hold: a job skips ticks (at worst until the TTL) or runs twice (today's behavior); no data effect, all bodies idempotent. expire_at failing raises like release does today (safe_run logs it once). One git revert restores today's code; a lease held by the new code expires by its TTL, so no cleanup. No terraform, IAM, SSM or environment-name change.

## Assumptions to verify

- Verified 2026-11-18 in the installed schedule library: Job.run sets last_run and calls _schedule_next_run after job_func returns, so the next run counts from the end of the previous one.
- moto supports UpdateItem with a ConditionExpression over two attributes (it does for PutItem/DeleteItem here; confirm in the conformance run).

## Open questions (recommendation each)

- OQ1: one PR or split. Recommend one PR: ~150 lines, 8 files; moving the legacy Tier-2 jobs is how they get the hold, so it is behavior, not a mechanical refactor; the host Tier-1 move is two lines. Alternative: 64.1 (hold) then 64.2 (registrations).
- OQ2: hold above the TTL. Recommend capping the hold at the TTL (reliability.md: "the TTL stays the maximum hold"; ShedLock requires lockAtMostFor >= lockAtLeastFor). The upgrade job's 900 s TTL under a 30 min interval then holds 15 min: covers the observed 0.7 s gap and any boot gap under 15 min. Alternative: reject TTL < interval at registration, which fails startup in production today unless upgrade_lease_ttl_seconds is raised in the same PR.
- OQ3: where the hold lives. Recommend a new primitive method expire_at plus a not_before keyword on LeaseStore.release (one conditional write per backend, ports to Redis PEXPIREAT under a compare script, a Postgres UPDATE ... WHERE owner). IdempotencyStore does not expose it.
- OQ4: AC #1 reword. Recommend: "BackgroundJobRegistry.register_interval and register_daily (lease_ttl None = Tier-1, a value = Tier-2; TASK-145.5.7.1) are the widened Protocol, and their docstrings state when a job first runs". No single register(schedule=...) value type: three call sites would churn for no new capability.
- OQ5: dependencies. TASK-64 depends on TASK-127 and TASK-148, both To Do. Recommend removing both: 148's purpose for 64 (a per-job TTL) is met by get_lease_store(ttl) since 145.5.7.1, and 127 decides the health-check sweep's fate, not how it registers. Notes on 127 and 148 record it.
- OQ6: margin as a setting. Recommend [scheduler] lease_hold_margin_seconds (default 5), a typed setting, not a constant (CLAUDE.md config rule). It is a technical value, not organisation policy.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (TASK-145.5.7 planning, human approved): TASK-145.5.7.1 adds the Tier-2 part of AC#1/#2: a lease_ttl: timedelta | None keyword on BackgroundJobRegistry.register_interval and register_daily (None = Tier-1; a value = the host wraps the job in run_if_leased with that TTL, taken from the job's own settings, never the scheduler default). The rest of this task stands: the declarative tier/schedule Protocol, host jobs moved onto it, _tier2 deleted, the default TTL kept for modules jobs (reliability.md 2026-11-04).

2026-11-04 (TASK-145.5.7.3 planning, human approved): (1) when safe_run moves into the registry adapter it keeps logging a failed run once at error with the traceback (logger.exception, added by TASK-145.5.7.3); job bodies never log and re-raise (reliability.md). (2) The widened schedule expression (AC1) states when a job first runs (after one interval, today's schedule-library default, or at registration), so no job relies on the library default; record it in reliability.md.

2026-11-18 (human approved OQ1-OQ6 as recommended): split refactor first into TASK-64.1 (ACs #1-#5: registrations through the registry, no behavior change; row 18f.1) and TASK-64.2 (AC #6: minimum hold, hold = min(TTL, interval - [scheduler] lease_hold_margin_seconds), primitive expire_at, LeaseStore.release(not_before=); row 18f.2). AC #1 reworded to the existing register_interval/register_daily shape plus first-run timing. Dependencies on TASK-127 and TASK-148 removed (148's per-job TTL is met by get_lease_store(ttl) since 145.5.7.1; 127 decides the sweep's fate, not its registration). Tests move time with freezegun (testing.md:30). TASK-145.9.2 and TASK-147.6 wait on 64.2.

2026-11-18: ACs #1-#5 verified by TASK-64.1 (implemented, in review once pushed); AC #6 is TASK-64.2.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 16:33

---

Placeholder IDs resolved: 'THIS TASK'/'TASK-A' in the description = TASK-64 (this task); 'TASK-B' = TASK-65 (strangle the pull-hub into feature hookimpls). Predecessor TASK-6 rewritten 2026-07-28 to the minimal single-default-TTL scope; this task delivers the declarative tier/TTL/schedule registry that lets features (and the eventual migrated modules jobs) declare leasing through the boundary.

---

created: 2026-09-14 15:27

---

2026-09-14: AC#4 registers integration_healthchecks as a host-owned Tier-1 job. TASK-92 (service health model, AC#4) decides whether that log-only vendor-probe job should exist at all, or be replaced by per-dependency metrics or a narrower credential probe. Re-check AC#4 against TASK-92's outcome before planning. Current state: jobs/scheduled_tasks.py integration_healthchecks guards each entry against exceptions, and the 'aws' entry uses build_identity_center_adapter (TASK-25.2.3.2.4).

---

created: 2026-09-24 20:07

---

2026-09-24 alignment with decisions/plugin-architecture.md: the widened BackgroundJobRegistry Protocol is the scheduler contract and moves to app/contracts/ with the hookspecs (TASK-107). The runtime that applies safe_run and the Tier-2 lease moves to app/server/scheduler/ (TASK-52, rescoped: server/, not infrastructure/). The lease comes from the coordination contract (TASK-58). This task still lands in place under app/jobs/ first, as planned; its placeholder reference 'TASK-B' is TASK-65.

---

created: 2026-09-25 15:00

---

2026-09-25: TASK-92 was narrowed to the service health model; the fate of integration_healthchecks moved to TASK-127, now a dependency. Re-check AC#4 against TASK-127 before planning.

---

created: 2026-11-18T00:01:00Z

---

2026-11-18 (human, from TASK-145.7.8's first production dry run): run_if_leased releases at job end (infrastructure/coordination/lease.py:14-17), so the incident legacy upgrade dry run, which takes under a second, ran on both replicas 0.7 s apart and logged two reports per interval. reliability.md now requires a minimum hold (ShedLock lockAtLeastFor). New AC added. Ordering: this task, or a subtask split from it under the size gate, lands before TASK-145.9.2 (stale-channel nudge) and TASK-147.6 (postmortem reminders) register their leased jobs; both now depend on it. The upgrade job needs no change: its writes are guarded.

---

created: 2026-11-18T18:48:00Z

---

2026-11-18 program-scope assessment of OQ1-OQ6 (human asked). Read: decisions/ (reliability, plugins, configuration, testing, cloud-portability), doc-11 (rows 18f, 18.L8, 12, Q1), doc-15 and doc-16 (no reference to TASK-64, leases or the scheduler; open PRs #1867 and #1870 touch none of jobs/, coordination/ or reliability.md), prior tasks 145.5.7.1, 145.5.7.3, 145.7.8, upcoming 145.9.2, 147.6, 145.12.3, 83.5, 165.10, 100, 148, 127, 52, 65.

OQ1 one PR or split. ADR: CLAUDE.md size gate ("mixing mechanical refactor with behavior change MUST be decomposed"). Prior: the human rule "combine dark slices" applies to no-consumer slices only; both slices here change production code. Web: Google eng-practices, refactorings in their own CL and a refactoring-only CL first when it makes the change cleaner (https://google.github.io/eng-practices/review/developer/small-cls.html). Conflict with my first answer: the registrations move is separable as a pure refactor (the registry already wraps safe_run and run_if_leased with the same TTL and lease names). Revised recommendation: split, refactor first: TASK-64.1 registrations (no behavior change), then TASK-64.2 hold (behavior, all Tier-2 jobs at once). 145.9.2 and 147.6 depend on 64.2.

OQ2 hold above the TTL. ADR: reliability.md:32 "the TTL stays the maximum hold" (settled). Web: ShedLock rejects lockAtLeastFor > lockAtMostFor (LockConfiguration: "lockAtLeastFor is longer than lockAtMostFor"), and its 15-minute example holds 14m (https://github.com/lukas-krecan/ShedLock). Gap: the ADR does not say how the hold is derived. Fix: hold = min(TTL, interval - margin), so the invariant holds by construction and no registration is rejected; reliability.md states the formula. Prior: 145.5.7.3 OQ17 sized the upgrade job TTL (900 s) to its run, not to the interval; it stays. Upgrade job holds 15 min.

OQ3 where the hold lives. ADR-backed: reliability.md:32 "through a conditional update under its claim token, never a delete"; :20 ownership rule; cloud-portability.md:23 the in-memory store is the hosting contract's fake, so it implements expire_at and the conformance suite covers both. Web: ShedLock's DynamoDB provider unlocks with UpdateItem "set lockUntil = :lockUntil" (later of now and lockAtLeastUntil), unconditionally; ours is stricter (token condition, ADR :20). Redis ports as a token-checked expiry change (redis-py Lock.extend(replace_ttl=True), https://redis.readthedocs.io/en/stable/lock.html). Upcoming: TASK-148 moves the claim's duration onto the call (the same direction: an expiry carried per call); TASK-100's fail-open lease holds no record, so its release with not_before frees nothing too (note on 100).

OQ4 AC #1 shape. ADR-backed: plugins.md:53 (schedule, tier and lease TTL as value types) and reliability.md:32 (2026-11-04: the Tier-2 part is lease_ttl on register_interval and register_daily). Gap: first-run timing (reliability.md:32 defers it to TASK-64). Web: APScheduler's interval trigger and the schedule library both first run one interval after scheduling; APScheduler offers next_run_time to override. No current or planned job (145.9.2 daily, 147.6, 145.12.3, 83.5 hourly, 165.10) needs another first run. Fix: state the timing, no first_run parameter; reword AC #1.

OQ5 dependencies. TASK-148: its blocker reason (a per-job TTL through the registry) is met since 145.5.7.1 by the per-TTL get_lease_store, which reliability.md:32 still names as current. TASK-127: decides the health-check sweep's fate, not its registration ("nothing on the critical path waits"). Recommend removing both dependencies, with notes on 148, 127 and 100.

OQ6 margin. ADR-backed: CLAUDE.md "config centralized and typed, no ad-hoc constants"; configuration.md:37 the base file holds every default, so [scheduler] lease_hold_margin_seconds = 5 in base.toml. Web: ShedLock caveat, clock differences above the hold can run a task twice; 5 s covers the whole-second expiry, the 1 s poll and replica skew. Technical value, not organisation policy.

Correction found: decisions/testing.md:30 makes freezegun the time tool; the planned clock keywords are dropped.

---
<!-- COMMENTS:END -->
