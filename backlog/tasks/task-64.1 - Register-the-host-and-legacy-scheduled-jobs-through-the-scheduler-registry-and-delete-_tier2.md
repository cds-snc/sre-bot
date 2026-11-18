---
id: TASK-64.1
title: >-
  Register the host and legacy scheduled jobs through the scheduler registry and
  delete _tier2
status: In Progress
assignee: []
created_date: '2026-11-18T19:00:00Z'
updated_date: '2026-11-18T19:35:00Z'
labels:
  - architecture
  - reliability
milestone: m-4
dependencies: []
references:
  - decisions/reliability.md
  - decisions/plugins.md
parent_task_id: TASK-64
priority: medium
ordinal: 528000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor slice of TASK-64 (approved 2026-11-18, refactor first; CLAUDE.md size gate). jobs/scheduled_tasks.py init() schedules the two host Tier-1 jobs and the three legacy Tier-2 jobs with direct schedule.every calls and wraps the Tier-2 ones in _tier2, bypassing the registry adapter that already applies safe_run and run_if_leased for feature jobs. Move all five onto the registry with no behavior change (same schedules, safe_run, lease names scheduler:<job_name>, the shared default TTL), delete _tier2, and state first-run timing in the registry docstrings and decisions/reliability.md. TASK-64.2 then adds the minimum hold to every Tier-2 job at once.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 init() registers scheduler_heartbeat and integration_healthchecks through registry.register_interval every 5 minutes as Tier-1 (no lease_ttl), and no schedule call in init() bypasses the registry (parent AC #2, #4)
- [x] #2 provision_aws_identity_center (every 2 h), notify_stale_incident_channels (daily 16:00, only with a Slack tenant) and spending_generate_spending_data (daily 00:00) register through the registry with lease_ttl = [scheduler] default_tier2_lease_ttl_seconds; their lease keys stay scheduler:<job_name> as before (parent AC #4, #5)
- [x] #3 _tier2 is deleted and no registration site contains a lease or error-boundary wrapper of its own (parent AC #2, #3)
- [x] #4 BackgroundJobRegistry's docstrings and decisions/reliability.md state when a job first runs: an interval job one interval after registration, a daily job at the next HH:MM UTC (parent AC #1)
- [x] #5 The legacy_surface job-run pins and the existing scheduler tests pass; tests that pinned the direct schedule calls or _tier2 are rewritten against the registry, not deleted
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-18 against main 98918309 (doc-11 row 18f.1). One PR from an up-to-date main on task-64.1-registry-registrations; the uncommitted planning set rides with it (TASK-64, 64.1, 64.2, 100, 127, 148, 145.9.2, 147.6, TASK-176 notes; decisions/reliability.md). Pure refactor: no schedule, boundary, lease name or TTL changes. The shared research and the approved OQs are on TASK-64 (plan and 2026-11-18 comment).

## Call sites

- jobs/scheduled_tasks.py:147-148 heartbeat and health checks: schedule.every(5).minutes.do(safe_run(...))
- jobs/scheduled_tasks.py:151 provision: schedule.every(2).hours.do(safe_run(_tier2("scheduler:provision_aws_identity_center", ...)))
- jobs/scheduled_tasks.py:153-159 nudge: Slack tenant gate, every().day.at("16:00"), _tier2("scheduler:notify_stale_incident_channels", ...), else scheduled_job_skipped debug
- jobs/scheduled_tasks.py:161-163 spending: every().day.at("00:00"), _tier2("scheduler:spending_generate_spending_data", ...)
- jobs/scheduled_tasks.py:126-134 _tier2 (TTL get_scheduler_settings().default_tier2_lease_ttl_seconds, get_lease_store(ttl), run_if_leased)
- jobs/scheduled_tasks.py:43-104 registry: register_daily -> schedule_lib.every().day.at(s).do(safe_run(...)); register_interval -> schedule_lib.every(seconds).seconds.do(safe_run(...)); _leased_or_plain -> get_lease_store(ttl) and run_if_leased(store, f"scheduler:{job_name}", job); debug event feature_background_job_scheduled
- contracts/scheduler/registry.py:10-51 Protocol docstrings
- Tests pinning today's shape: tests/unit/jobs/test_scheduled_tasks.py (imports _tier2; TestTier2Wrapper :190-250; TestInitJobRegistration :252-372 patches _tier2 and schedule.every; TestStaleIncidentChannelsJob :383-420 patches _tier2), tests/integration/jobs/test_scheduled_tasks_integration.py:29-86 (string-matches ".minutes.do(", ".hours.do("), tests/unit/jobs/test_jobs_scheduled_tasks_startup_logging.py:35 (event name)
- Pins that must stay green unchanged: tests/integration/legacy_surface/test_aws_identity_center_provision_job_run.py, test_incident_stale_channel_job_run.py, test_aws_spending_data_update_job_run.py (they import the job bodies, not init); tests/integration/legacy_surface/INVENTORY.md:97-103 cites line numbers (doc update)

## Equivalence (why no behavior changes)

- Intervals: every(5).minutes == every(300).seconds and every(2).hours == every(7200).seconds in the schedule library (both set interval and unit; next run = now + interval).
- Daily: identical every().day.at("HH:MM").do(...).
- Boundary: both paths wrap in safe_run once.
- Lease: the registry leases under f"scheduler:{job_name}", so job names provision_aws_identity_center, notify_stale_incident_channels and spending_generate_spending_data keep the exact DynamoDB keys; TTL timedelta(seconds=default_tier2_lease_ttl_seconds) reaches the same get_lease_store(1800) singleton; a lease held by the old code at deploy is honoured by the new.
- Only visible differences: the debug registration event now also appears for host and legacy jobs (renamed, below), and a failed legacy run's safe_run_error names the job body (module and function copied by _leased_or_plain) instead of _tier2's inner "wrapped".

## Steps (TDD)

1. Tests first (red):
   a. New tests/unit/jobs/test_jobs_scheduler_init_registrations.py: init() with a recording BackgroundJobRegistry (the registry class in jobs.scheduled_tasks replaced by a fake that records register_interval/register_daily calls; jobs/ is outside the strict seam zone) asserts exactly: scheduler_heartbeat and integration_healthchecks interval 5 min, lease_ttl None; provision_aws_identity_center interval 2 h, lease_ttl = default TTL; notify_stale_incident_channels daily "16:00" with lease_ttl = default TTL only when a Slack tenant is set (skip logged otherwise, as today); spending_generate_spending_data daily "00:00" with lease_ttl = default TTL; the plugin callback receives the same registry instance after the host jobs. A second test drives the real registry with the schedule library mocked and get_lease_store returning an in-memory LeaseStore: running the scheduled provision callable takes the lease key scheduler:provision_aws_identity_center with TTL 1800 (a pre-held key skips the run), proving the lease name is unchanged.
   b. tests/unit/jobs/test_scheduled_tasks.py: TestTier2Wrapper's three cases (first call runs, held lease skips, expired lease reruns) rewritten as registry cases with lease_ttl in tests/unit/jobs/test_jobs_scheduled_tasks_registry_lease.py where not already covered there (held-lease skip already is; add expired-lease rerun); TestInitJobRegistration and the two TestStaleIncidentChannelsJob init cases move to 1a's file (the per-run fresh-client case stays); _tier2 import removed.
   c. tests/integration/jobs/test_scheduled_tasks_integration.py: the three init tests assert on schedule_lib: five .do registrations, every(300).seconds twice, every(7200).seconds once, day.at("16:00") and day.at("00:00") once each, every scheduled callable wrapped by safe_run (a raising body is caught and logged once).
   d. tests/unit/jobs/test_jobs_scheduled_tasks_startup_logging.py: event background_job_scheduled.
2. jobs/scheduled_tasks.py: init() builds the registry first, registers the five jobs through it (job names above; timedelta(minutes=5), timedelta(hours=2), "16:00", "00:00"; lease_ttl=timedelta(seconds=get_scheduler_settings().default_tier2_lease_ttl_seconds) for the three Tier-2 jobs; the Slack tenant gate and its skip log unchanged), then calls register_plugin_jobs(registry). Delete _tier2 and the run_if_leased-only imports it used if no longer needed. Rename the debug event feature_background_job_scheduled -> background_job_scheduled (it now covers host and legacy jobs; debug only, no consumer outside the test). Class docstring: the adapter binds host, legacy and feature jobs.
3. contracts/scheduler/registry.py: Protocol docstring (host and feature jobs); register_interval: first run one interval after registration, restarted by every deploy; register_daily: first run at the next HH:MM UTC. No signature change.
4. decisions/reliability.md: already edited in the planning session (first-run timing, registrations through the adapter, hold formula, Checks, Changes line); confirm the text matches the code.
5. tests/integration/legacy_surface/INVENTORY.md:97-103: line references and "registered through the scheduler registry".
6. Gates: ruff, targeted tests during TDD; then make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams; full mypy, then full pytest, once each, sequential.

## AC traceability

- AC #1 (host Tier-1 through the registry) -> step 2 -> 1a, 1c
- AC #2 (legacy Tier-2 through the registry, TTL and lease keys) -> step 2 -> 1a (both tests)
- AC #3 (_tier2 deleted, no wrapper at sites) -> step 2 -> 1b (import gone), rg _tier2 empty
- AC #4 (first-run timing) -> steps 3, 4 -> review (docstrings, ADR)
- AC #5 (pins green; tests rewritten not deleted) -> step 1 -> legacy_surface pins and the rewritten cases

## Size

~45 production lines changed (init ~-20/+30, _tier2 -9, event rename, docstrings ~10) over 2 production files; tests ~+150/-120; ADR and INVENTORY docs. Well under the gate; one subsystem.

## Blast radius and rollback

Merging deploys. If a registration were wrong, a job would run at another cadence or without its lease (duplicate run, absorbed by idempotent bodies) or not at all; the init tests pin each. Leases held across the deploy keep their keys and TTL. One git revert restores today. No terraform, IAM, SSM or environment-name change: deploy-checks not required. Human post-deploy check: the next heartbeat (5 min) and a running_integration_healthchecks line appear in the production logs.

## Assumptions

- The schedule library's every(n).seconds and every(m).minutes/hours compute the same next run for equal durations (checked in its Job._schedule_next_run: interval * unit as a timedelta).
- The safe_run log naming change is acceptable (it improves the field).

## Open questions

None: the shape, split and ADR text were approved on TASK-64 (2026-11-18).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-18: implemented (TDD) on the working tree from main 98918309 (branch task-64.1-registry-registrations created by the human). jobs/scheduled_tasks.py: init() builds the registry first and registers scheduler_heartbeat and integration_healthchecks (5 min, Tier-1), provision_aws_identity_center (2 h), notify_stale_incident_channels (daily 16:00, Slack tenant gate and skip log unchanged) and spending_generate_spending_data (daily 00:00), the three with lease_ttl = default_tier2_lease_ttl_seconds, so the lease keys stay scheduler:<job_name>; then the plugin callback. _tier2 deleted. Debug event renamed background_job_scheduled. contracts/scheduler/registry.py docstrings state first-run timing (decisions/reliability.md edited at planning). Tests: new tests/unit/jobs/test_jobs_scheduler_init_registrations.py (recording registry: exact registrations, skip without tenant, plugin callback after the host jobs, client per run; real registry: lease key scheduler:provision_aws_identity_center, TTL 1800, a held lease skips); TestTier2Wrapper's expired-lease case moved to test_jobs_scheduled_tasks_registry_lease.py (the other two were already covered there); init cases in test_scheduled_tasks.py moved to the new file, the spending run case kept; integration init tests assert exact cadences (300 s x2, 7200 s x1, 16:00 and 00:00) and the safe_run boundary on a raising host job; INVENTORY.md references. Gates: ruff OK; contracts 14 kept; key ownership OK; package shape 3 baselined; seams 47/12; mypy 40 errors in 13 files (baseline, none in touched files); pytest 7679 passed. ACs #1-#5 checked; In Progress.
<!-- SECTION:NOTES:END -->
