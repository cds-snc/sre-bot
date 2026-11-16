---
id: TASK-145.7.6
title: >-
  VideoCall in core: features/incident/meet moves to
  core/adapters/google_meet.py
status: Done
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T22:10:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 503000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4b (approved program in TASK-145.7's plan, section 2; outline in the parent plan). Mechanical move plus a VideoCall Protocol (create -> OperationResult[VideoCallReference]) and fake; no subject kwarg (TASK-145.6 AC #7); modules/incident/core.py:12 repointed; features/incident/meet/ deleted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 features/incident/meet does not exist; core/adapters/google_meet.py and the VideoCall Protocol and fake exist with tests; the legacy import is repointed (checks parent AC #3)
- [x] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan 2026-11-10, grounded at main e9bcdcbc plus L4a (#1850, 02d01ee6 + 7e461f8f, open). APPROVED 2026-11-10 (OQ1 one-PR exception, OQ2 branch after #1850, OQ3 async port per R1-R5). Program row: TASK-145.7 plan section 2, L4b (~140 / 6, incident core move, no waits, one revert).

## 0. Found state

- features/incident/meet/: __init__.py (empty), adapters/__init__.py (empty), adapters/google_meet.py (37 lines): create_space(**kwargs) -> dict, pops delegated_user_email, builds get_meet_service(scopes=MEET_SCOPES), posts {"config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"}}, execute(num_retries=0), logs google_api_request_failed and re-raises HttpError.
- Callers: modules/incident/core.py:12 (import), :131 (recreate: create_space()["meetingUri"], inside try), :459 (legacy declare: create_space()["meetingUri"]). No caller passes delegated_user_email (only the test does).
- Test: tests/unit/features/incident/meet/adapters/test_incident_meet_adapter.py (4 tests; one asserts the delegated kwarg is passed).
- Guardrails naming meet: app/pyproject.toml:398 (incident-umbrella layers, exhaustive), features/incident/README.md:20, :36, :47, :126 (:20 and :126 point video calls at a lifecycle/ subdomain, stale since TASK-145.7's plan put the adapter in core).
- Pattern to follow (L4a, TASK-145.6): IncidentReport Protocol in core/api.py (sync, runtime_checkable, classified results, no delegation subject), GoogleDocsIncidentReport in core/adapters/google_docs.py, InMemoryIncidentReport in core/adapters/in_memory.py, get_incident_report() lru_cache provider, one parity suite over adapter + fake, test_incident_core_report_no_delegation.py source scan over core/adapters.
- VideoCallReference already exists in core/domain.py:209 and is exported by core/api.py; the record already stores the video_call reference kind. No new entity.

## 1. Steps

1. core/adapters/google_meet.py (new, git-detected rename of meet/adapters/google_meet.py):
   - create_space() moved verbatim minus the **kwargs / delegated_user_email (no delegation subject: TASK-145.6 AC #7 rule; no caller passes it). Kept for the two legacy calls; deleted with the legacy declare (145.7.10) and recreate (145.8.6).
   - GoogleMeetVideoCall.create() (async def) -> OperationResult[VideoCallReference]: runs the same blocking request (shared private _create_space_request) through asyncio.to_thread inside the adapter, bounded by the gateway's per-attempt httplib2 timeout and num_retries=0; a fresh service and Http per call (client.py builds one per call, outbound-clients.md thread rule); HttpError and refused credentials classified with classify_google_error into an error result (status, error_code, retry_after), logged as incident_video_call_create_failed; missing google_workspace.tenant -> PERMANENT_ERROR CONFIG_NOT_CONFIGURED before any call; a response with no name or meetingUri -> transient error; success -> VideoCallReference(system=GOOGLE, tenant=customer_id, vendor_id=name ("spaces/..."), url=meetingUri).
   - link(call) -> str | None returns the stored url (same as IncidentReport.link); a non-Google reference is not served (None).
2. core/api.py: VideoCall Protocol (runtime_checkable; async def create(), sync link(call) since link reads the stored url and does no I/O; docstring rules: no delegation subject, classified results, never exceptions, the adapter offloads blocking calls). get_video_call() lru_cache provider returning GoogleMeetVideoCall(). Both added to __all__ and the module docstring.
3. core/adapters/in_memory.py: InMemoryVideoCall(tenant=..., fail_with=None): async create() returns a Google reference with a counter vendor_id and a meet.google.com url, records created calls; fail_with returns that error result; link as the adapter.
4. modules/incident/core.py:12: `from features.incident.core.adapters import google_meet as meet` (call sites :131, :459 unchanged).
5. Delete features/incident/meet/ (three files) and tests/unit/features/incident/meet/ (the test moves, step 7).
6. app/pyproject.toml:398: drop meet from the incident-umbrella layer. features/incident/README.md: delete the meet/ row (:20), drop meet at :36 (and the already-gone documents/drive there), :47, and :126 points video calls at core/adapters/google_meet.py behind VideoCall.
7. Tests (tests/unit/features/incident/core/):
   - test_incident_core_video_call_create_space.py: the four moved legacy tests, the delegated one replaced by "the factory is called with scopes only".
   - test_incident_core_video_call_protocol_parity.py: adapter (stubbed get_meet_service, configured tenant) and fake: create returns a Google reference under the tenant with the meet url; link returns the stored url; both satisfy isinstance(VideoCall).
   - test_incident_core_video_call_errors.py: adapter only: 429 -> transient with retry_after, 403 -> classified status, refused credentials -> UNAUTHORIZED, missing tenant -> CONFIG_NOT_CONFIGURED and no request built, empty response -> error; execute(num_retries=0) and the request body pinned.
   - test_incident_core_report_no_delegation.py: the recorder also replaces get_meet_service and runs create() once (the source scan already covers core/adapters).
   - test_incident_core_api_surface.py: VideoCall and get_video_call in __all__.
8. decisions/outbound-clients.md (R1): the async-port rule after :30 (a port consumed from async code is async def; an adapter over a blocking SDK offloads inside its own methods with asyncio.to_thread, bounded by the SDK per-attempt timeout, since a running thread cannot be cancelled; to_thread copies contextvars; callers never offload; a sync port only while every consumer is sync, each listed under Migration; async-native vendor clients replace to_thread when first-party, GA and on the gateway's credential source, so google-apps-meet waits), a Migration entry listing the sync ports with async consumers (incident ports until TASK-145.8.7; RecordStore, ConditionalWriteStore and the directory, spreadsheet and drive providers until TASK-25), the default-pool sizing risk, and a change-log line. Written to the working tree 2026-11-10; rides with this PR. decisions/transport-slack.md:73: the reader tolerance names TASK-145.8.7. decisions/workplace-systems.md:69: "stays in features/incident/scheduling and features/incident/meet" becomes scheduling and core/adapters/google_meet.py. decisions/incident-management.md: change-log line (2026-11-xx, TASK-145.7.6): meet/ dissolved into core/adapters/google_meet.py behind VideoCall; drop meet from the tolerated-siblings line (:133) wording as done. doc-11 row 18.L4b notes updated in the same session (never committed).

## 2. AC traceability

- AC #1: steps 1-5, 7 (create_space, parity, errors, surface tests; meet/ gone checked by lint-imports + rg).
- AC #2: step 6 and the gates: ruff, lint-imports, make check-package-shape, make check-test-seams, targeted tests during TDD; then full mypy, then full pytest once each.
- Parent AC #3 checked by AC #1.

## 3. Test matrix

| Case | File |
| --- | --- |
| happy: legacy create_space body, scopes only, num_retries=0, returns payload | ..._video_call_create_space.py |
| failure: create_space propagates HttpError and unclassified errors (legacy contract unchanged) | ..._video_call_create_space.py |
| happy: await create -> VideoCallReference (Google, tenant, spaces/ id, url), adapter and fake; the adapter runs the request off the event loop (to_thread observed) | ..._video_call_protocol_parity.py |
| boundary: link returns stored url; foreign-system reference -> None | ..._video_call_protocol_parity.py |
| failure: 429/403/credentials refused/unknown exception classified; missing tenant before any call; empty response | ..._video_call_errors.py |
| boundary: no delegation subject reaches the gateway | ..._report_no_delegation.py |
| idempotency: none offered (Meet has no idempotency key); pinned that retries are off | ..._video_call_errors.py |

## 4. Assumptions and doubts

- No other importer of features.incident.meet: rg over the repo (excluding backlog/) finds only modules/incident/core.py:12, the one test and the prose at decisions/workplace-systems.md:69 (step 8); re-run before deleting.
- Unknown exceptions: classify_google_error propagates them (client.py:381); the adapter does the same (no blanket except), as google_docs does.
- Async port over a sync SDK: to_thread copies contextvars, so structlog bindings reach the adapter's logs; the thread is not cancellable, so the per-attempt timeout bounds it; the default executor (min(32, cpu+4)) is shared, a per-vendor limiter waits for TASK-33.
- Legacy behaviour is unchanged: both legacy callers ignore kwargs and read meetingUri.

## 5. Size gate, blast radius, rollback

- Production: google_meet.py ~75 (37 moved), api.py ~30, in_memory.py ~30, modules/incident/core.py 1, pyproject.toml 1, README ~6, two ADRs ~3; meet/ deleted (3 files). ~145 changed LOC, 8 files plus 3 deletes; one subsystem (incident core). Mechanical move + additive inert Protocol in one PR as the approved program row (OQ1).
- Blast radius: legacy declare and recreate video-call creation (import path only). A wrong import fails at boot/import, caught by pytest and lint-imports. One git revert restores meet/.
- No config, terraform, IAM or SSM change: no deploy checks.

## 6. Domain-model evolution

Not applicable: VideoCallReference and the video_call reference kind exist (TASK-145.5/145.7.7); no new entity, field or stored shape. vendor_id is the Meet space name (spaces/<id>), url the meeting uri, matching how the legacy upgrade will re-reference meet links only by url (no change here).

## 7. Decisions (human, 2026-11-10)

- OQ1: one PR (move plus the inert Protocol), a recorded exception to size-gate rule 3.
- OQ2: branch task-145.7.6-video-call from main after #1850 (L4a) merges.
- OQ3 (program-scope assessment, comment of 2026-11-10): R1 async-port rule in outbound-clients.md; R2 VideoCall.create is async with to_thread inside the adapter; R3 TASK-145.8.7 (L3b, stacked on L3, before L6a and 145.7.9) converts IncidentReport, IncidentTranscriptReader, IncidentStore and StatusUpdateStore; R4 RecordStore and the platform providers stay sync, a TASK-25 divergence; R5 google-apps-meet deferred until GA and on the gateway's credential source.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 implemented (TDD) on task-145.7.6-video-call from main dcb8a08d. core/adapters/google_meet.py (moved from meet/adapters, create_space without the delegated kwarg; GoogleMeetVideoCall async create via asyncio.to_thread of the shared _create_space_request, classified HttpError/GoogleCredentialsRefused, CONFIG_NOT_CONFIGURED without a tenant, transient on an incomplete payload, link only for Google). core/api.py VideoCall Protocol + get_video_call; InMemoryVideoCall; modules/incident/core.py import repointed; features/incident/meet and its tests deleted; incident-umbrella layer drops meet; README, workplace-systems.md:69, incident-management.md (tolerated-siblings line, change log) updated; outbound-clients.md and transport-slack.md edits ride along. Tests: video_call_create_space (4), video_call_protocol_parity (adapter+fake, off-loop thread pinned), video_call_errors, no_delegation and api_surface extended. Gates: ruff clean; lint-imports 13 kept 0 broken; check-package-shape and check-test-seams OK (no net-new); mypy 40 errors / 13 files (baseline 41/14, none in touched files); pytest tests --ignore=tests/smoke 7140 passed. Agent ran git mv for the move by mistake: the rename is staged in the index (human unstages or commits as is).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T20:50:00Z

---

2026-11-10 (human): OQ1 approved: one PR (move plus the inert VideoCall Protocol), a recorded size-gate rule 3 exception. OQ2 approved: branch task-145.7.6-video-call from main after #1850 (L4a) merges. OQ3 (sync vs async Protocol) not approved: to be assessed against the ADRs, doc-11, doc-15, prior and upcoming tasks and current practice before approval.

---

created: 2026-11-10T20:53:00Z

---

2026-11-10 OQ3 program-scope assessment (PROPOSED, awaiting human approval). Gap: decisions/outbound-clients.md:30 (Accepted) says blocking SDK calls from async code go through asyncio.to_thread, but says nothing about whether a port is async or where the offload sits. Conflict in practice: scribe/service.py:298 (async) calls the sync IncidentReport (:333, :411) and IncidentTranscriptReader (:286) with no offload; production code has no offload anywhere today. Prior: IncidentConversation async (145.6.3), IncidentReport/IncidentStore/StatusUpdateStore sync; transport-slack.md:73 keeps the reader sync until its callers are async (scribe's already is). Upcoming async consumers: 145.7.9 declare (including POST /incidents on FastAPI's loop), 145.8.x cutovers, 145.9.1, 145.11; TASK-33 (async Bolt). Practice (Azure SDK guidelines, Google generated *AsyncClient, FastAPI/Litestar docs): ports are async when consumers are async; the sync-backed adapter offloads inside itself, bounded by the SDK timeout (a running thread cannot be cancelled); to_thread copies contextvars. Async-native: google-apps-meet SpacesServiceAsyncClient exists but is Beta/preview, gRPC outside the gateway factory; no official async Docs/Drive/Calendar; google.auth.aio has no external_account (AWS federation). Proposal: R1 ADR rule (async ports, adapter offloads, callers never do); R2 L4b VideoCall async with to_thread in the adapter; R3 new stacked layer above L3 converting IncidentReport, IncidentTranscriptReader (AsyncWebClient), IncidentStore and StatusUpdateStore to async; R4 RecordStore and other platform Protocols stay sync, recorded as a tolerated divergence under TASK-25; R5 google-apps-meet deferred until GA and on the gateway's credential source.

---

created: 2026-11-10T21:00:00Z

---

2026-11-10 (human): plan approved. OQ1 one-PR exception, OQ2 branch after #1850 merges, OQ3 recommendations R1-R5 approved (async VideoCall.create with to_thread in the adapter; ADR rule in outbound-clients.md; TASK-145.8.7 created for the other incident ports; RecordStore and providers under TASK-25; google-apps-meet deferred).

---
<!-- COMMENTS:END -->
