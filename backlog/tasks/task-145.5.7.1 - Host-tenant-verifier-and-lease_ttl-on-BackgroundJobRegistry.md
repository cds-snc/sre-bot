---
id: TASK-145.5.7.1
title: Host tenant verifier and lease_ttl on BackgroundJobRegistry
status: In Progress
assignee: []
created_date: '2026-11-04T14:04:00Z'
updated_date: '2026-11-04T18:19:00Z'
labels:
  - incident
  - reliability
  - workplace
dependencies:
  - TASK-157
references:
  - decisions/workplace-systems.md
  - decisions/reliability.md
  - decisions/outbound-clients.md
parent_task_id: TASK-145.5.7
priority: medium
ordinal: 473000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of 3 of TASK-145.5.7 (Stack K layer on top of #1735; branch stack-k/task-145.5.7.1-host-tenant-verifier-and-lease). Host and contracts only; nothing in features uses it yet, so revert is behavior-neutral.

D1 (approved 2026-11-04): tenant verification is host-owned. New Protocol TenantVerifier in app/contracts/workplace/ (beside ConfiguredSystems, exported from contracts/workplace/__init__.py) returning the verified tenant id for a WorkplaceSystem as an OperationResult (UNAUTHORIZED on mismatch with the expected and received ids; a classified error on a failed call). Host implementation in app/server/tenant_verification.py: auth.test through the integrations/slack client factory, classify_slack_error, verdict by the UNCHANGED check_slack_tenant/TenantMismatch from server/slack/tenant_guard.py (TASK-157, #1817). Registered in the svcs registry beside ConfiguredSystems (server/services.py CORE_SERVICES). Only Slack is implemented; Google returns unsupported until a batch writer needs it. No integrations/slack/tenant.py; the vendor package shape and #1817 are unchanged.

D2 (approved): lease_ttl: timedelta | None = None keyword on BackgroundJobRegistry.register_interval and register_daily (contracts/scheduler/registry.py; host adapter jobs/scheduled_tasks.py). None = Tier-1 (today's behavior); a value = Tier-2 via run_if_leased(get_lease_store(ttl), f"scheduler:{job_name}", ...). The TTL comes from the job's own settings, never the scheduler default (decisions/reliability.md). This is the Tier-2 slice of TASK-64 AC#1/#2; TASK-64 stays open for the rest.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TenantVerifier Protocol exists in contracts/workplace/, is exported from contracts.workplace, and returns an OperationResult carrying the verified tenant id (tested with a structural fake)
- [x] #2 The Slack host verifier calls auth.test through the integrations/slack client factory and judges the returned team_id and enterprise_id with the unchanged check_slack_tenant: matches (team only, enterprise only, both) return the configured tenant id; a team mismatch, an enterprise mismatch and an Enterprise org the entry does not name return UNAUTHORIZED naming the expected and received ids
- [x] #3 A failed auth.test call returns the status classify_slack_error gives (and a PERMANENT error for an unclassified exception) with no token in the result or logs; no [slack.tenant] entry and the Google system each return a not-configured / unsupported error without any call
- [x] #4 TenantVerifier is registered in the svcs registry at startup beside ConfiguredSystems; startup resolution makes no Slack call
- [x] #5 register_interval and register_daily accept lease_ttl: timedelta | None = None; None leaves every current registration unchanged; a value wraps the job in run_if_leased with get_lease_store(ttl) and the name scheduler:<job_name>; a non-positive TTL is rejected at registration
- [x] #6 Verified by targeted tests, ruff, then once mypy and once full pytest, from app/; make check-import-contracts is green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (2026-11-04, human-approved decisions D1 and D2 of TASK-145.5.7). Planned against main dc79aa33 (TASK-157 / #1817 is merged there) + #1735. STATUS: awaiting human review.

GATE: ~7 production files, ~170 production LOC, one subsystem (host: contracts + server + jobs). Passes. Revert = no behavior change (nothing in features consumes either addition; lease_ttl defaults to None).
WAITS FOR: TASK-157 deployed with its Slack smoke recorded (slack_tenant_mismatch = 0): this verifier reuses its verdict and must not ship on an unverified tenant rule. The merge is already on main.

1. GROUNDING (path:line)
- ConfiguredSystems contract: app/contracts/workplace/configured_systems.py:15; export app/contracts/workplace/__init__.py:3-6.
- Registered at startup: app/server/services.py:56 _build_configured_systems, :62-66 CORE_SERVICES (CoreService(ConfiguredSystems, ...) at :65), :84-90 register_core_services, initialize_core_services resolves every CoreService once at startup (so the TenantVerifier factory must build without calling Slack).
- Verdict: app/server/slack/tenant_guard.py:40 TenantMismatch(expected_team_id, expected_enterprise_id, received_team_id, received_enterprise_id), :49 check_slack_tenant(tenant: SlackTenant, *, team_id, enterprise_id) -> TenantMismatch | None. SlackTenant.tenant_id = enterprise_id or team_id (integrations/slack/settings.py; #1817). Unchanged by this task.
- Client + classifier: app/integrations/slack/client.py:37 get_slack_web_client(), :67 classify_slack_error(exc) -> (OperationStatus, code, retry_after); it RE-RAISES an unclassified exception (:67-74, :85), so the verifier must catch that. server may import integrations (contract b forbids only packages/features/infrastructure; host_configuration.py:43 already imports integrations.slack.settings).
- OperationResult: app/contracts/operations/result.py:47 success, :68 error, :121 permanent_error; statuses contracts/operations/status.py:10-24 (UNAUTHORIZED, PERMANENT_ERROR); codes registry contracts/operations/codes.py:19 (test tests/unit/contracts/operations/test_error_code_registry.py fails on unregistered literals). Existing: UNSUPPORTED_OPERATION (:109), CONFIG_NOT_CONFIGURED (:31). New codes needed: TENANT_MISMATCH, TENANT_CHECK_FAILED.
- Registry Protocol: app/contracts/scheduler/registry.py:10-39 (register_daily :22, register_interval :31). Host adapter app/jobs/scheduled_tasks.py:25-69 (_ScheduleBackgroundJobRegistry; safe_run only, no lease), _tier2 :84-92 (default TTL via get_scheduler_settings().default_tier2_lease_ttl_seconds), get_lease_store(ttl_seconds) infrastructure/coordination/factory.py:37 (jobs/ may import infrastructure), run_if_leased infrastructure/coordination/lease.py:8.
- Existing tests: tests/unit/contracts/scheduler/test_scheduler_contracts_registry_protocol.py, tests/unit/jobs/test_scheduled_tasks.py, tests/unit/server/test_server_services_registration.py, tests/unit/server/test_server_services_configured_systems_resolve.py, fixtures tests/factories/services.py, tests/factories/slack.py.

2. ORDERED STEPS (exact files) - TDD, tests first per step
S1 app/contracts/operations/codes.py: add TENANT_MISMATCH, TENANT_CHECK_FAILED (alphabetical, 2 lines). [AC2, AC3]
S2 app/contracts/workplace/tenant_verifier.py (new, ~25 LOC): Protocol TenantVerifier with
   def verified_tenant(self, system: WorkplaceSystem) -> OperationResult[str]
   (sync, like the Slack Web client and the scheduler jobs). Docstring: success data = the tenant id the system's vendor confirmed for the configured entry (equals ConfiguredSystems.tenants()[system]); UNAUTHORIZED/TENANT_MISMATCH with expected and received ids when the vendor reports another tenant; the classified status on a failed call; PERMANENT_ERROR/CONFIG_NOT_CONFIGURED when the system has no tenant entry; PERMANENT_ERROR/UNSUPPORTED_OPERATION when no verifier exists for the system. Export from app/contracts/workplace/__init__.py. [AC1]
S3 app/server/tenant_verification.py (new, ~70 LOC): HostTenantVerifier implementing TenantVerifier (a dispatch on system). SLACK -> _verify_slack(): tenant = get_slack_settings().tenant (None -> permanent_error CONFIG_NOT_CONFIGURED); try client = get_slack_web_client(); response = client.auth_test(); except Exception as exc: try classify_slack_error(exc) -> OperationResult.error(status, f"Slack auth.test failed: {code}", TENANT_CHECK_FAILED) (retry_after kept for transient via transient_error); if classify re-raises, PERMANENT_ERROR/TENANT_CHECK_FAILED naming type(exc).__name__ only (never str(exc): may echo request detail; never the token). team_id/enterprise_id = response.get(...) normalised (non-str or blank -> None). mismatch = check_slack_tenant(tenant, team_id=..., enterprise_id=...); mismatch -> OperationResult.error(OperationStatus.UNAUTHORIZED, "Slack tenant mismatch: expected team_id=.. enterprise_id=..; received team_id=.. enterprise_id=..", TENANT_MISMATCH) and one structured WARNING (ids only); none -> success(data=tenant.tenant_id). GOOGLE (and any other) -> permanent_error UNSUPPORTED_OPERATION (Google lands with its first batch writer). Imports: server.slack.tenant_guard, integrations.slack.client/settings, contracts only. Async: sync call, documented; it runs inside a scheduler thread. [AC2, AC3]
S4 app/server/services.py: _build_tenant_verifier() -> TenantVerifier returning HostTenantVerifier() (cheap: no settings read, no client built; both resolved per call); add CoreService(TenantVerifier, _build_tenant_verifier) after the ConfiguredSystems row (:65). initialize_core_services logs count (now 4). [AC4]
S5 app/contracts/scheduler/registry.py: add keyword lease_ttl: timedelta | None = None to register_daily (:22) and register_interval (:31); docstring: None = Tier-1 (runs on every replica); a value = Tier-2, at most one replica per interval; the lease is a duplication optimisation, the job body must stay idempotent; the TTL comes from the job's own settings and is sized to its max run (decisions/reliability.md). [AC5]
S6 app/jobs/scheduled_tasks.py: add helper _leased(name, job, ttl: timedelta) -> reject ttl <= 0 with ValueError at registration; ttl_seconds = int(ttl.total_seconds()); lock_store = get_lease_store(ttl_seconds); wrapped = run_if_leased(lock_store, name, lambda: job()). Reuse it from _tier2 is NOT done (that is TASK-64's contraction). _ScheduleBackgroundJobRegistry.register_daily/register_interval take lease_ttl; job_to_run = job if lease_ttl is None else _leased(f"scheduler:{job_name}", job, lease_ttl); then safe_run(job_to_run) as today; the debug event adds lease_ttl_seconds. Order: safe_run outside the lease, same as init() at :109-122. [AC5]
S7 Test doubles for the next slice: tests/factories/tenant_verifier.py (new) FakeTenantVerifier(results: Mapping[WorkplaceSystem, OperationResult[str]]) recording calls; used by 145.5.7.2. (Test code, not counted in the gate.)

3. AC -> STEP -> TEST
AC1: S2 -> tests/unit/contracts/workplace/test_workplace_tenant_verifier_protocol.py (FakeTenantVerifier satisfies the Protocol structurally; exported from contracts.workplace).
AC2: S1, S3 -> tests/unit/server/test_server_tenant_verification_slack.py (team-only match; enterprise-only match; both match; team mismatch; enterprise mismatch; Enterprise org returned while entry names none -> mismatch naming ids; entry names team only and auth.test returns team + enterprise -> mismatch (D10 case, asserted so the first production dry run is understood); success data == tenant.tenant_id).
AC3: S1, S3 -> same file: invalid_auth -> UNAUTHORIZED, ratelimited -> TRANSIENT with retry_after, unknown exception -> PERMANENT TENANT_CHECK_FAILED, token/str(exc) absent from the result message and captured logs (log capture fixture); no [slack.tenant] -> CONFIG_NOT_CONFIGURED and auth_test never called; GOOGLE -> UNSUPPORTED_OPERATION and no call. tests/unit/contracts/operations/test_error_code_registry.py stays green.
AC4: S4 -> tests/unit/server/test_server_services_tenant_verifier_resolve.py (modelled on test_server_services_configured_systems_resolve.py: resolves HostTenantVerifier from the registry; initialize_core_services with Slack unconfigured and a client factory that raises on any call: no call made); update tests/unit/server/test_server_services_registration.py count/list.
AC5: S5, S6 -> tests/unit/contracts/scheduler/test_scheduler_contracts_registry_protocol.py (extended: both methods accept lease_ttl, default None) and tests/unit/jobs/test_jobs_scheduled_tasks_registry_lease.py (None: job not leased, get_lease_store not called, existing registrations unchanged; value: get_lease_store called with int seconds, run_if_leased called with scheduler:<job_name>, job runs once when lease acquired and not when held; exception in the job still reaches safe_run; ttl 0 and negative -> ValueError; daily and interval both). Existing tests/unit/jobs/test_scheduled_tasks.py stays green.
AC6: gates below.
Enabling-only: S7.

4. TEST MATRIX
Happy: five Slack match cases; lease acquired runs once; Tier-1 unchanged. Boundary: ttl 1 s ok, 0 and negative rejected; blank/None/non-str ids from auth.test normalised to absent. Failure: classified Slack errors (unauthorized, transient, not-found), unclassified exception, unconfigured Slack, Google. Authorization: mismatch variants. Idempotency: lease held -> job skipped.

5. ASSUMPTIONS AND HOW TO VERIFY
A1 auth.test response supports .get (slack_sdk SlackResponse is mapping-like; the core adapter reads it that way at features/incident/core/adapters/slack.py:207-215): verify in the test with the real SlackResponse type.
A2 classify_slack_error reads settings for the error lists (get_slack_settings): tests use the existing settings fixtures in tests/factories/slack.py.
A3 The org-token auth.test shape (enterprise_id present for an org install while production [slack.tenant] names team_id only) is D10, an assumption confirmed only by the first production dry run; if wrong, the production tenant entry needs enterprise_id (a config change, not code) before apply.
A4 Adding a CoreService does not break server startup tests that count services: verify tests/unit/server/test_server_services_*.py.
A5 jobs/ may import infrastructure.coordination (already does, jobs/scheduled_tasks.py:11).

6. BLAST RADIUS AND ROLLBACK
New Protocol, one host class, one registry row, one optional keyword defaulting to None: no consumer, no behavior change at merge. Risk: a bug in the CoreService factory fails startup for every deployment (the factory is trivial and tested). git revert of the PR restores everything; no data, config or ordering constraint. 145.5.7.2 depends on this slice.
Gates after implementation: ruff, targeted tests, then once mypy and once full pytest; make check-import-contracts.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved): plan approved as written, with D1-D10.

2026-11-04 implemented (TDD, tests first and red) on top of rebased #1735 (main 1420fbb5), as uncommitted work for branch stack-k/task-145.5.7.1-host-tenant-verifier-and-lease. 7 production files, +177/-7: contracts/operations/codes.py (TENANT_CHECK_FAILED, TENANT_MISMATCH); contracts/workplace/tenant_verifier.py (new Protocol, verified_tenant(system) -> OperationResult[str]) exported from contracts/workplace/__init__.py; server/tenant_verification.py (new HostTenantVerifier: settings and Web client read per call; Slack auth.test judged by the unchanged check_slack_tenant; mismatch UNAUTHORIZED/TENANT_MISMATCH naming expected and received ids plus one tenant_verification_mismatch warning; a failed call keeps classify_slack_error's status and retry hint with TENANT_CHECK_FAILED, and an unclassified exception is PERMANENT naming its type only; no entry CONFIG_NOT_CONFIGURED, Google UNSUPPORTED_OPERATION, both without a call); server/services.py (CoreService(TenantVerifier) after ConfiguredSystems; the factory reads nothing); contracts/scheduler/registry.py and jobs/scheduled_tasks.py (lease_ttl keyword on register_daily/register_interval; None leaves the job as is; a value wraps it in run_if_leased(get_lease_store(seconds), 'scheduler:<job_name>') inside safe_run; under one second is rejected at registration with ValueError: the plan said <= 0, but a sub-second TTL truncates to 0 s, so the bound is 1 s). _tier2 untouched (TASK-64's contraction). Tests: new test_server_tenant_verification_slack.py (5 match/mismatch cases incl. D10's unnamed Enterprise org, blank/non-str ids, 5 failure classes with no token in result or logs, unconfigured and Google make no call), test_contracts_workplace_tenant_verifier_protocol.py, test_server_services_tenant_verifier_resolve.py (startup resolves every core service with a Slack factory that raises), test_jobs_scheduled_tasks_registry_lease.py; updated the registry Protocol, registration, workplace export and scope-entry-point fake tests; tests/factories/tenant_verifier.py FakeTenantVerifier for 145.5.7.2. Gates from app/: uv run ruff check . -> All checks passed!; ruff format --check . -> 1105 files already formatted; targeted pytest (tests/unit/server, contracts, jobs, oncall_sync, access/sync, integration/server) green; make check-import-contracts -> Contracts: 13 kept, 0 broken; make check-settings-key-ownership -> OK; mypy . --exclude .venv (once) -> Found 41 errors in 14 files (checked 425 source files), all pre-existing, none in a touched file; pytest tests --ignore=tests/smoke (once) -> 6149 passed in 178.26s. ACs #1-#6 checked.
<!-- SECTION:NOTES:END -->
