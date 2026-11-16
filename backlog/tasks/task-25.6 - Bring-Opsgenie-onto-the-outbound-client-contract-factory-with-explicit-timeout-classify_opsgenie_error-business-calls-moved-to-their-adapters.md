---
id: TASK-25.6
title: >-
  Bring Opsgenie onto the outbound-client contract: factory with explicit
  timeout, classify_opsgenie_error, business calls moved to their adapters
status: In Progress
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-11-16T14:30:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/opsgenie/client.py
  - app/packages/oncall_sync/adapters/opsgenie.py
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1602
parent_task_id: TASK-25
priority: high
ordinal: 239000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every vendor in app/integrations/ conforms to decisions/outbound-clients.md; nothing is tolerated silently.

TODAY (re-verified 2026-11-16). app/integrations/opsgenie/client.py:
- urllib, with no factory and no classify_opsgenie_error. urlopen already passes timeout=settings.timeout_seconds, and settings are read at use (no import-time read). create_alert and the POST helper are already gone, so every Opsgenie call is a GET.
- Three business operations live in the vendor package (get_on_call_users, get_on_call_user_for_rotation, healthcheck) behind api_get_request, all re-exported from __init__.py.
- Broad 'except Exception' blocks swallow or re-wrap, so programmer errors become data.

CONSUMERS:
- packages/oncall_sync/adapters/opsgenie.py, a Path B adapter mapping OpsGenieAPIError to OnCallSyncError. TASK-146.1 builds the on-call capability over this client, and TASK-146.2 makes oncall_sync a feature over it and deletes this adapter.
- modules/incident/on_call.py (get_on_call_users), the legacy declare path, replaced by TASK-145.7.9/145.7.10.
- jobs/scheduled_tasks.py integration_healthchecks; TASK-127 decides whether that probe survives, so only its call path migrates here.

TARGET. The vendor package exports an async httpx client factory (explicit per-attempt timeout, connect-only retry set once at construction) and classify_opsgenie_error, plus its settings, and nothing else. The on-call operations move into the code that needs them: the oncall_sync adapter, a module-local helper for the legacy declare, and a private probe for the health check. Sync callers reach the async client through one asyncio.run at their edge (decisions/outbound-clients.md async-port rule).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/opsgenie/ exports only an async client factory (explicit per-attempt timeout, connect-only retry configured once at construction), classify_opsgenie_error and its settings; no business operation and no import-time settings read remain in the vendor package
- [x] #2 Each consumer calls the client inside try/except + classify_opsgenie_error at its boundary and reaches it through one asyncio.run at its sync edge; classified failures in the legacy declare helper return [] and never fail the declare; unexpected exceptions propagate instead of being logged and swallowed
- [x] #3 The vendor package has no write helper and every Opsgenie call is a GET (rg evidence in notes), so no non-idempotent write needs replay protection
- [x] #4 Classification tests cover each mapped failure family (including an unparseable body as INVALID_RESPONSE) plus one unmapped exception propagating; factory tests assert the timeout and retry settings; the oncall_sync adapter, legacy helper and health-check probe each have success, classified-failure and not-configured tests
- [x] #5 decisions/outbound-clients.md: the Opsgenie Migration line is removed, an unparseable vendor body is named as an expected failure family, and oncall_sync's Slack usergroup port is listed as a sync port with an async consumer until TASK-146.2
- [x] #6 ruff, mypy, pytest tests --ignore=tests/smoke, make check-vendor-package-contract, check-import-contracts, check-settings-key-ownership, check-package-shape and check-test-seams pass, with output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v2 (2026-11-16; approved decisions R1a, size exception and OQ6, human 2026-11-16; supersedes v1). Single side PR on branch task-25.6-opsgenie-outbound-client from an up-to-date main (doc-11 row 18c). Gates row 18d TASK-146.1, which gates 145.7.9.

CALL SITES (path:line, against main 0e12a616; re-grep at start)
- app/integrations/opsgenie/client.py:12 OpsGenieAPIError; :16 get_on_call_users; :29 get_on_call_user_for_rotation; :62 healthcheck; :85 api_get_request (urlopen).
- app/integrations/opsgenie/__init__.py:3-17 re-exports; settings.py:37-64; app/config/base.toml:158-162 [opsgenie].
- app/packages/oncall_sync/ports.py:22 OnCallScheduleProvider.get_current_on_call_email (sync); adapters/opsgenie.py:5-24; providers.py:11,24; service.py:46 sync_all, :115 _sync_rotation; __init__.py:25-30 _run_oncall_sync (job entry).
- app/modules/incident/on_call.py:6,:33; callers modules/incident/core.py:199 and :432 (legacy declare, sync Bolt).
- app/jobs/scheduled_tasks.py:14 import, :180 "opsgenie" entry in integration_healthchecks.
- Unchanged: server/plugins/requirements.py:25,44; server/configuration/host_configuration.py:41,236; oncall_sync keeps Requirement("opsgenie.tenant") until TASK-146.2.

DECISIONS
D1 (OQ1, R1a) Async client. build_opsgenie_client(settings=None) -> httpx.AsyncClient: base_url from the tenant's api_url, Authorization "GenieKey <key>", timeout=timeout_seconds (per attempt), transport=httpx.AsyncHTTPTransport(retries=connect_retries); the caller opens it per call as "async with". No network I/O at construction. Basis: the async-native rule in outbound-clients.md (TASK-145.7.6 R1), the TASK-25.10.1 OpenAI precedent, and TASK-145.8.7 AC #2 (sync entrypoints reach async code through asyncio.run only, at the edge). TASK-146.1's capability adapter awaits this client directly, with no to_thread.
D2 (OQ2, OQ5) httpx; new typed key [opsgenie] connect_retries (int, ge=0, default 2) in settings.py and base.toml, mirroring [openai]. No status-based retry, no loop.
D3 (AC #3) Zero Opsgenie writes: GET /v2/schedules/{id}/on-calls, GET /v2/schedules/{id}/timeline?identifierType=id&interval=1&intervalUnit=days, GET /v1/services. A connect-only retry never repeats a sent request. The exports test pins that no write helper exists; rg evidence goes in the notes.
D4 (OQ6, OQ8) classify_opsgenie_error(exc) -> (OperationStatus, error_code, retry_after), the OpenAI table: 401 UNAUTHORIZED/UNAUTHENTICATED, 403 UNAUTHORIZED/FORBIDDEN, 404 NOT_FOUND, 429 TRANSIENT/RATE_LIMITED with Retry-After seconds or None (Opsgenie documents 429 and X-RateLimit-State, not Retry-After), 5xx TRANSIENT/SERVER_ERROR, other 4xx PERMANENT/HTTP_ERROR, httpx.TimeoutException TRANSIENT/TIMEOUT, other httpx.HTTPError TRANSIENT/CONNECTION_ERROR, json.JSONDecodeError PERMANENT/INVALID_RESPONSE (new ErrorCode member; an unparseable body is an expected vendor outcome). Anything else is re-raised. A parsed body of the wrong shape stays adapter-level (explicit checks, an error outcome, never a caught KeyError).
D5 (OQ7) Each consumer checks the tenant first: not configured -> CONFIG_NOT_CONFIGURED outcome (adapter), [] with a warning (legacy helper), False (probe), before any call. The factory raises ValueError on a missing tenant only as a programmer-error guard.
D6 (R1a) oncall_sync goes async at the port: OnCallScheduleProvider.get_current_on_call_email is async def; OnCallSyncService.sync_all and its per-rotation and per-schedule helpers are async and await it; _run_oncall_sync bridges once per run with asyncio.run (one crossing per run). The Slack usergroup port (sync WebClient, user token) stays sync, called from the async service; it blocks only the job's own loop on the scheduler thread. It is listed under outbound-clients.md Migration as a sync port with an async consumer until TASK-146.2. The oncall_sync Opsgenie adapter maps classified failures and shape errors to OnCallSyncError (cause kept), so the service's error handling is unchanged; unexpected exceptions propagate.
D7 (OQ3) Legacy declare helper: module-local async _get_on_call_emails(schedule) in modules/incident/on_call.py, run with one asyncio.run from the sync get_on_call_users_from_folder. Classified failures, a wrong shape and a missing tenant return [] with a structured warning (decisions/oncall.md:20: a failing source never fails the declare; migration.md rule 1 bug fix). Only unclassified exceptions propagate.
D8 (OQ4) Health check: private probe in jobs/scheduled_tasks.py (async, GET /v1/services), run through asyncio.run in the dict entry; classified failure -> False with an error log, tenant None -> False. TASK-127 AC #3 decides its fate.

STEPS (TDD: failing tests first for each)
1. app/contracts/operations/codes.py: add INVALID_RESPONSE.
2. app/integrations/opsgenie/settings.py and app/config/base.toml: connect_retries (Keys docstring updated).
3. app/integrations/opsgenie/client.py: only build_opsgenie_client and classify_opsgenie_error (and the private Retry-After helper). OpsGenieAPIError, the three operations, api_get_request, urllib and the logger are deleted. __init__.py exports build_opsgenie_client, classify_opsgenie_error, OpsGenieSettings, OpsGenieTenant (if exported today) and get_opsgenie_settings.
4. app/packages/oncall_sync/ports.py: get_current_on_call_email async def. adapters/opsgenie.py: async GET timeline in try/except (httpx.HTTPError, json.JSONDecodeError) -> classify -> OnCallSyncError from exc; explicit shape checks; period and recipient logic unchanged. service.py: sync_all and helpers async, await the schedule provider; Slack target calls unchanged. __init__.py: _run_oncall_sync runs asyncio.run(service.sync_all()).
5. app/modules/incident/on_call.py: D7.
6. app/jobs/scheduled_tasks.py: D8; opsgenie removed from the module import.
7. decisions/outbound-clients.md: item 1 httpx line unchanged (async); item 2 names an unparseable vendor body as an expected family classified PERMANENT_ERROR INVALID_RESPONSE, while a parsed body of the wrong shape is the adapter's to report; Migration: Opsgenie line removed; oncall_sync's Slack usergroup port added to "sync ports with async consumers" until TASK-146.2; Changes entry 2026-11-xx (TASK-25.6). decisions/oncall.md: no change (line 18 already names the TASK-25.6 client).
8. Task files via CLI: 146.1 note, 146.2 AC, 25.10.3 AC (done at approval, 2026-11-16).

TESTS (app/tests; httpx.MockTransport at the HTTP edge; async tests with the repo's asyncio marker)
- tests/unit/integrations/opsgenie/test_opsgenie_client_build.py: base_url, GenieKey header, timeout, AsyncHTTPTransport built with retries=connect_retries (recording stand-in as in the OpenAI factory test), no socket opened at construction, tenant None -> ValueError. AC #1, #4.
- tests/unit/integrations/opsgenie/test_opsgenie_client_classify_error.py: 401, 403, 404, 429 with and without Retry-After, 500, 418, timeout, connect error, JSONDecodeError -> INVALID_RESPONSE, KeyError propagates. AC #4.
- tests/unit/integrations/opsgenie/test_opsgenie_package_exports.py: __all__ is the allowed set; no write helper. Settings test gains connect_retries default and validation. AC #1, #3.
- tests/unit/packages/oncall_sync/test_oncall_sync_opsgenie_adapter.py (rewritten, async): user recipient, team recipient -> None, future startDate -> None, rotation absent -> None, 500 / timeout / bad JSON / wrong shape -> OnCallSyncError with cause, tenant None -> OnCallSyncError (CONFIG_NOT_CONFIGURED), unexpected bug propagates. AC #2, #4.
- tests/unit/packages/oncall_sync/test_oncall_sync_service.py and tests/integration/legacy_surface/test_oncall_sync_job_run.py: fakes of the schedule provider become async; behaviour assertions unchanged apart from awaiting (the pin still drives the job entry). Plus one test that _run_oncall_sync runs sync_all once per run. AC #2.
- tests/modules/incident/test_incident_on_call.py: classified failure -> [], tenant None -> [], wrong shape -> [], happy path names, unexpected exception propagates. AC #2, #4.
- tests/integration/jobs/test_scheduled_tasks_integration.py (patch target updated) and new tests/unit/jobs/test_jobs_opsgenie_healthcheck_run.py: healthy, classified unhealthy, tenant None, unexpected exception reaches the per-check handler. AC #2, #4.
- tests/integrations/opsgenie/test_opsgenie_client.py deleted (cases moved above).

AC TRACE: #1 steps 2-3, build and exports tests; #2 steps 4-6, adapter, service, legacy and probe tests; #3 D3, exports test and rg evidence; #4 classify, build, adapter, legacy and probe tests; #5 gates.
GATES: ruff and targeted tests during; at the end, once each and in sequence: mypy, then pytest tests --ignore=tests/smoke; make check-vendor-package-contract, check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams. Output recorded in notes.

SIZE: about 11 production files (codes.py, settings.py, base.toml, client.py, __init__.py of opsgenie, oncall_sync ports.py, adapters/opsgenie.py, service.py, __init__.py, modules/incident/on_call.py, jobs/scheduled_tasks.py) plus outbound-clients.md; about 250 production LOC; one vendor and its three consumers. Size-gate rule 3 exception APPROVED (human, 2026-11-16): port colour change plus a contained bridge, one revert.

ASSUMPTIONS AND HOW TO VERIFY
- No running event loop in the threads that call the bridges: the scheduler thread (run_continuously) and legacy sync Bolt handlers. Precedent: scribe and comms entrypoints already call asyncio.run from sync Bolt handlers. Verify that core.py:199/:432 run in sync handlers only.
- The legacy pin test_oncall_sync_job_run fakes the provider seam: its fake becomes async; check the pin's seam entry and the test-seam guard.
- No other importer of integrations.opsgenie: rg at start.
- No env-name, terraform, IAM or SSM change, so no deploy-checks; connect_retries has a default.

BLAST RADIUS AND ROLLBACK
- Ships wrong: oncall_sync stops updating usergroups (logged per rotation; the job boundary catches the rest), legacy declare loses on-call names in the boilerplate (never fails it), the health check logs unhealthy. No writes to Opsgenie or to persistence. One git revert restores all of it, with no ordering constraint.
- Merge conflict: TASK-25.5 edits the same healthcheck dict (maxmind line); whichever merges second rebases.
- Program scope: 146.1 moves the adapter's reads into capabilities/oncall/adapters/opsgenie.py and awaits the client; 146.2 deletes the oncall_sync adapter and ports.py, makes the Slack port async (or offloads in its adapter) and removes its Migration entry; 145.7.9/145.7.10 delete the legacy helper; 127 decides the probe; doc-15 E2 removes Opsgenie before 2027-04-05.

DOMAIN-MODEL EVOLUTION: not applicable (one error-code member, one setting; no entity added or reshaped).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16 OQ program-scope assessment (PROPOSED, awaiting human approval; supersedes plan v1 D1, D7, the 146.1 to_thread note and D4's ValueError/INVALID_RESPONSE wording where they differ).
OQ1 SETTLED, plan v1 conflicts. outbound-clients.md async-port rule (TASK-145.7.6 OQ3 R1-R5, 2026-11-10): to_thread is for blocking SDKs only; an async-native client replaces it when first-party, GA and on the gateway's own credential source. An httpx client built by our own factory with the GenieKey header qualifies, and TASK-25.10.1 built httpx.AsyncClient. TASK-145.8.7 AC #2: sync entrypoints reach async code through asyncio.run only, at the edge. So: build_opsgenie_client returns httpx.AsyncClient with AsyncHTTPTransport(retries=connect_retries), used per call as async with (OpenAI shape). 146.1's capability adapter awaits it directly, with no to_thread. Consumers: (R1a, recommended) oncall_sync's OnCallScheduleProvider becomes async def, sync_all async, the job entry _run_oncall_sync bridges once per run with asyncio.run (one crossing per run, as the Django async guidance advises); oncall_sync's Slack usergroup port stays sync and is listed under Migration as a sync port with an async consumer until TASK-146.2 (it blocks only the job's own loop on the scheduler thread). Legacy declare helper: one asyncio.run in modules/incident/on_call.py. Healthcheck: asyncio.run inside the private probe. Alternative (R1b): keep oncall_sync sync, with asyncio.run inside its Opsgenie adapter per rotation, deleted by 146.2. Rejected: sync-over-async below the edge, one loop and client per rotation. Size with R1a is about 11 production files and about 250 LOC, one file over the gate: rule-3 exception (port colour change plus a contained bridge, one revert).
OQ2 SETTLED: httpx (outbound-clients.md Changes 2026-11-09, TASK-25.10.1).
OQ3 DECIDED for the new path (oncall.md:20, a failing source invites nobody and never fails the declare); legacy applies it as a migration.md rule 1 bug fix; 145.7.9/146.3 own the new path, 145.7.10 deletes the helper.
OQ4 OWNED by TASK-127 AC #3; this task migrates the call path only (reliability.md background-job boundary unchanged).
OQ5 SETTLED: [openai] connect_retries default 2 (TASK-25.10.1).
OQ6 GAP: classify_openai_error does not map json.JSONDecodeError (a non-JSON 200 propagates as a bug); Meet's incomplete payload is an adapter-level transient error with no code (145.7.6). Proposal: outbound-clients.md item 2 names an unparseable vendor body as an expected family (PERMANENT_ERROR, new ErrorCode.INVALID_RESPONSE; botocore treats a parse failure as a response error, not a bug); a parsed body of the wrong shape stays adapter-level. TASK-25.10.3 gains an AC to map it for OpenAI.
OQ7 SETTLED by precedent (Meet, Sheets, MaxMind, OpenAI summarizer): the adapter checks the tenant first and returns PERMANENT_ERROR CONFIG_NOT_CONFIGURED; the factory raises ValueError on a missing tenant only as a programmer-error guard.
OQ8 Opsgenie documents 429 and X-RateLimit-State, not Retry-After (docs.opsgenie.com/docs/api-rate-limiting); the classifier returns None when Retry-After is absent, as OpenAI does.
Scope changes proposed: TASK-146.1 note (OnCallLookup async def; the Opsgenie adapter awaits the async client, no to_thread); TASK-146.2 AC (the Slack usergroup port goes async or offloads inside its adapter, and its Migration entry is removed); TASK-25.10.3 AC (OQ6).

2026-11-16 (human): R1a approved with the size-gate rule 3 exception (~11 production files), and the OQ6 ADR fix approved. Plan v2 written; ACs reworded (old #3 and #4 tightened, ADR AC added, gates widened) and description TODAY corrected.

2026-11-16 implemented (TDD) on task-25.6-opsgenie-outbound-client from main f5176b80, In Progress; ACs #1-#6 checked one by one against the evidence below.
#1 integrations/opsgenie/: client.py holds build_opsgenie_client (httpx.AsyncClient, base_url from [opsgenie.tenant] api_url, GenieKey header, timeout=timeout_seconds per attempt, AsyncHTTPTransport(retries=connect_retries); ValueError without a tenant, a programmer-error guard) and classify_opsgenie_error (OpenAI table + json.JSONDecodeError -> PERMANENT_ERROR INVALID_RESPONSE); __init__ exports those two plus OpsGenieSettings, OpsGenieTenant, get_opsgenie_settings; OpsGenieAPIError, get_on_call_users, get_on_call_user_for_rotation, healthcheck, api_get_request and urllib deleted. New [opsgenie] connect_retries (int >= 0, default 2; base.toml). New ErrorCode.INVALID_RESPONSE.
#2 Consumers: packages/oncall_sync/adapters/opsgenie.py (async; settings and client factory injectable; classified failures, unexpected shape and not configured -> OnCallSyncError with the code and cause; unexpected exceptions propagate); ports.py OnCallScheduleProvider async; service.py sync_all/_sync_schedule/_sync_rotation async; __init__._run_oncall_sync runs asyncio.run once per job run. modules/incident/on_call.py: module-local get_on_call_users (one asyncio.run; not configured, classified failure and wrong shape -> [] with a warning; unexpected propagates); callers are sync Bolt handlers (incident.submit, incident_helper.recreate_missing_incident_resources). jobs/scheduled_tasks.py: _opsgenie_healthcheck (asyncio.run over _probe_opsgenie; GET /v1/services; the old log of the whole response body dropped).
#3 rg: no .post/.put/.patch/.delete/.request on the Opsgenie client; the three calls are client.get (jobs/scheduled_tasks.py:194 /v1/services, modules/incident/on_call.py:37 on-calls, packages/oncall_sync/adapters/opsgenie.py:50 timeline). Exports test pins no write helper.
#4 Tests: tests/unit/integrations/opsgenie/test_opsgenie_client_build.py, test_opsgenie_client_classify_error.py, test_opsgenie_package_exports.py, settings load (+connect_retries); tests/unit/packages/oncall_sync/test_oncall_sync_opsgenie_adapter.py (rewritten over httpx.MockTransport), test_oncall_sync_service.py (async fakes); tests/modules/incident/test_incident_on_call.py (+6 helper tests); tests/unit/jobs/test_jobs_opsgenie_healthcheck_run.py; tests/integration/jobs/test_scheduled_tasks_integration.py (patch target); legacy pin test_oncall_sync_job_run.py (its fake source async, assertions unchanged); test_configuration_files_vendors.py base pin (+connect_retries). tests/integrations/opsgenie/test_opsgenie_client.py deleted (cases moved).
#5 decisions/outbound-clients.md: item 2 names an unparseable vendor body (PERMANENT_ERROR INVALID_RESPONSE; wrong shape is the adapter's); Migration: Opsgenie line removed, oncall_sync UserGroupSyncTarget added to sync ports with async consumers until TASK-146.2; Changes 2026-11-16.
#6 Gates (from app/): ruff check . -> All checks passed!; make check-vendor-package-contract -> OK (15 baselined, no Opsgenie entry); check-import-contracts -> 13 kept, 0 broken; check-settings-key-ownership -> OK; check-package-shape -> OK (3 baselined); check-test-seams -> OK (47 strict, 12 legacy baselined); mypy . -> first run 41 errors / 14 files, one new in modules/incident/on_call.py:60 (fixed), rerun Found 40 errors in 13 files = the main baseline, none in touched files; pytest tests --ignore=tests/smoke -> 7258 passed, 194 warnings in 228.47s.
Size: 11 production files (+ADR), size-gate rule 3 exception approved 2026-11-16. Rollout: no env-name, terraform, IAM or SSM change, so no deploy-checks; connect_retries has a default. After deploy, read the opsgenie_healthcheck_success / integration_healthcheck_result lines and an oncall_sync_rotation_synced line.
<!-- SECTION:NOTES:END -->
