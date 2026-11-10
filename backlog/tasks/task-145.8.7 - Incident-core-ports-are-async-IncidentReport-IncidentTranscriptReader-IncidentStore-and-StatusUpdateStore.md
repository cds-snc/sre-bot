---
id: TASK-145.8.7
title: 'Incident stores are async: IncidentStore and StatusUpdateStore'
status: In Progress
assignee: []
created_date: '2026-11-10T21:00:00Z'
updated_date: '2026-11-10T22:32:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.8.1
references:
  - decisions/outbound-clients.md
  - decisions/transport-slack.md
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
ordinal: 521000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L layer L3b, stacked on TASK-145.8.1 (L3) before TASK-145.8.3 (L6a). Applies the async-port rule (decisions/outbound-clients.md, approved 2026-11-10 on TASK-145.7.6 OQ3 R1/R3) to the two incident stores: every IncidentStore method (including L3's update_fields, set_roles and set_status) and every StatusUpdateStore method is async def; RecordIncidentStore and RecordStatusUpdateStore offload each call's sync RecordStore work with one asyncio.to_thread inside the adapter (RecordStore stays sync until TASK-25); the in-memory fakes are async. Callers await: the command check find_incident_for_conversation, comms/service (draft, form, approval, publication, history) and scribe/service.py; the three sync Bolt handlers that reach a now-async service (status-update command, New update, History) call it through asyncio.run, as the comms handlers already do (until TASK-33). Split at full planning (size gate, human 2026-11-10): IncidentReport and IncidentTranscriptReader move to TASK-145.8.8 (row L3c, a side PR after this merges); until then start_status_update_draft and scribe still call the sync reader and report from async code, listed under the decisions' Migration entries for TASK-145.8.8. TimelineStore stays sync: its only consumers are the store bodies inside the offloaded call.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IncidentStore (get, find_by_conversation, list_open, read_security_flag, create, attach_conversation, set_reference, update_fields, set_roles, set_status) and StatusUpdateStore (append, latest, list_for_incident, transition) methods are async def in core; RecordIncidentStore and RecordStatusUpdateStore run each call's RecordStore work off the event loop with one asyncio.to_thread inside the adapter; the in-memory fakes are async; no caller wraps a store call in to_thread
- [x] #2 find_incident_for_conversation and every comms/ and scribe/ caller await the stores; the sync Bolt handlers reach them through asyncio.run only; behaviour tests unchanged apart from awaiting and async fake overrides
- [x] #3 outbound-clients.md Migration drops IncidentStore and StatusUpdateStore from its sync-port list and names TASK-145.8.8 for IncidentReport and IncidentTranscriptReader; transport-slack.md's IncidentTranscriptReader tolerance names TASK-145.8.8; features/incident/README.md says the stores are async
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Base: branch stack-l/task-145.8.7-async-ports, added by `gh stack add` on top of L3 (stack-l/task-145.8.1-core-updates, 11b63483) after L3 is synced onto main (0e12a616, which carries TASK-145.7.5 and 145.7.6). L3 does not touch comms/ or scribe/; it adds update_fields, set_roles and set_status to IncidentStore, plus TimelineStore. Line numbers below: core/store.py and core/adapters/in_memory.py are from 11b63483, everything else from main.

Approach (mechanical; no behaviour change):
- The Protocols change colour (`def` -> `async def`). Each Record adapter keeps its current sync body and gets one `asyncio.to_thread` per public call (outbound-clients.md async-port rule: the adapter offloads, callers never do). A call that makes several RecordStore requests (find_by_conversation's bindings-then-item read; L3's guarded write with its re-read and timeline append) is one offload, not one per request. The thread runs the existing sync code unchanged, and to_thread copies the context, so the structlog bindings reach the adapter's logs.
- Shape: rename the current sync classes to private `_RecordIncidentStoreCalls` and `_RecordStatusUpdateStoreCalls` (bodies untouched, no Protocol base), and make `RecordIncidentStore` / `RecordStatusUpdateStore` thin async adapters with the same constructor signatures. They build the private instance and forward each method as `return await asyncio.to_thread(self._calls.<method>, ...)`. This keeps the diff to signatures plus forwards, keeps L3's internal calls between methods sync, and leaves build_incident_store and build_status_update_store unchanged.
- TimelineStore stays sync. Its consumers are RecordIncidentStore's body (inside the offload) and InMemoryIncidentStore. No async code calls it, so the rule's "sync allowed while every consumer is sync" holds. TASK-145.9.x converts it when it gains an async consumer (noted on 145.9.2 at its planning).
- IncidentReport and IncidentTranscriptReader are TASK-145.8.8 (L3c). Until it lands, start_status_update_draft becomes async but still calls the sync reader through _read_window; this is the same sync-in-async that scribe already has, and is listed under Migration for 145.8.8.

Steps:
1. core/store.py (11b): IncidentStore Protocol :199-313, all 10 methods (get :221, find_by_conversation :225, list_open :237, read_security_flag :241, create :245, attach_conversation :257, set_reference :271, update_fields :282, set_roles :294, set_status :302) become `async def`. StatusUpdateStore Protocol :981-1020, all 4 (append :993, latest :1001, list_for_incident :1005, transition :1009) become `async def`. RecordIncidentStore :331 is renamed `_RecordIncidentStoreCalls` and the new async RecordIncidentStore forwards the 10 methods. RecordStatusUpdateStore :1022 is renamed the same way, with 4 forwards. Docstrings say each call runs in one worker thread. (AC #1)
2. core/adapters/in_memory.py (11b): InMemoryStatusUpdateStore :83 (append :89, transition :96, latest :110, list_for_incident :115) and InMemoryIncidentStore :132 (get :163 through set_status :294) public port methods become `async def`. Any port method that calls another port method awaits it. Test helpers (bind, seed, entries, _apply, _write) stay sync. (AC #1)
3. core/api.py: find_incident_for_conversation :446 becomes `async def` and awaits store.find_by_conversation. The re-exports are unchanged. (AC #2)
4. comms/service/draft.py: start_status_update_draft :82 and save_status_update_draft :158 become async. generate_status_update_draft :239 is already async. _security_gate :410, _append :520 and _append_new :543 become async. Awaits are added at the find calls :117/:195/:300, list_for_incident :123/:200/:306, append :222/:527/:550, latest :231/:535 and read_security_flag :425, plus the awaits of the helpers. _read_window :442 stays sync (reader, 145.8.8). (AC #2)
5. comms/service/form.py: start_status_update_form :37 becomes async and awaits start_status_update_draft :51. save_status_update_form :74 awaits save_status_update_draft :103. (AC #2)
6. comms/service/approval.py: await list_for_incident :47/:92, transition :129 and latest :137 (the functions are already async). comms/service/publication.py: _read_approved :157 becomes async (await :159), and its four async callers (:40, :~60, :102, :120) await it; await transition :84. comms/service/history.py: get_status_update_overview :20 becomes async and awaits :39/:43. (AC #2)
7. comms/entrypoints/slack.py: the three sync handlers that now reach an async service wrap the call in asyncio.run inside the open scope, as :395/:423/:526 already do: handle_status_update_command :244 (get_status_update_overview), handle_new_update_action :278 (start_status_update_form) and handle_history_action :449 (get_status_update_overview). _incident_scope and _status_update_scope are unchanged. The other handlers already run their service through asyncio.run. (AC #2)
8. scribe/service.py: await find_incident_for_conversation :260 (draft_incident_document_from_conversation is already async). scribe/entrypoints/slack.py is unchanged: it already calls asyncio.run at :187/:248. (AC #2)
9. decisions/outbound-clients.md:79 Migration: drop IncidentStore and StatusUpdateStore from the entry and rename it to "IncidentReport and IncidentTranscriptReader (called without an offload from scribe/service.py and comms/service/draft.py), until TASK-145.8.8". Update the :96 Changes line, and add a dated Changes line for the split. decisions/transport-slack.md:73 and :90: "until TASK-145.8.8". decisions/incident-management.md: one Changes line only if it names 145.8.7's scope (check at implementation). features/incident/README.md core row: the stores are async; their Record adapters offload each call with one to_thread. (AC #3)
10. Tests (TDD order: steps 10a-10b fail first, then 1-8, then 10c):
   a. Extend tests/unit/features/incident/core/test_incident_core_api_surface.py. Assert inspect.iscoroutinefunction for the 14 IncidentStore/StatusUpdateStore Protocol methods, for the Record adapters' and fakes' methods, and for find_incident_for_conversation (the file already does this for IncidentConversation). Update its _RecordingStore :199 to async.
   b. New tests/unit/features/incident/core/test_incident_core_incident_store_offload.py and test_incident_core_status_update_store_offload.py. A RecordStore fake records threading.get_ident() on each call. Awaiting a RecordIncidentStore/RecordStatusUpdateStore method from a running loop runs the RecordStore call on a thread other than the loop's (one representative read and one guarded write each, with find_by_conversation covering the two-read path). A structlog contextvar bound before the await is visible to the adapter's log line (capture_logs). A RecordStore failure still comes back as the classified OperationResult, not an exception.
   c. Mechanical: the existing ~51 test files that call the stores, the fakes, find_incident_for_conversation or the converted comms services become `async def test_...` (asyncio_mode = "auto", pyproject.toml:118) and await those calls. The ~15 test-local subclasses that override fake port methods (e.g. comms/test_incident_comms_status_update_approval.py :219/:271/:363/:484/:503, _save.py :78/:93/:98, _generate_instructions.py :116/:183/:197/:202) become `async def`. tests/factories/incident.py is updated where it calls store methods. Assertions are unchanged; mypy's unused-coroutine and attr-defined errors are the completeness check that no call was missed. Entrypoint and dispatch tests (comms entrypoint tests, integration/features/incident/comms/*_dispatch.py, integration/legacy_surface/test_incident_updates_command_surface.py) pass unchanged apart from async fake overrides; they prove the sync Bolt handlers still work through asyncio.run.

AC traceability:
- #1: steps 1-2; tests 10a (colour), 10b (offload off-loop, context, classified failure), 10c (existing store behaviour tests, now awaited, prove behaviour unchanged).
- #2: steps 3-8; tests 10a (find_incident_for_conversation), 10c (comms/scribe service, entrypoint and dispatch tests, unchanged assertions).
- #3: step 9; reviewed in the diff.
- #4: gates in the order CLAUDE.md sets: ruff and targeted tests during TDD; lint-imports, check-package-shape and check-test-seams; then full mypy once, then full pytest once.

Test matrix:
- Happy: every store method is awaited and returns the same OperationResult as before (existing store tests, 10c); comms start/save/generate/approve/publish/history flows unchanged (existing comms tests); Bolt command and actions update the modal (entrypoint and dispatch tests).
- Boundary: find_by_conversation's bindings miss then by_channel fallback is one offload (10b plus the existing find_by_conversation_bindings tests); L3's guarded write conflict re-read stays inside one call (existing update_fields and upgrade_on_write tests, awaited).
- Failure: RecordStore unavailable or conflict returns the classified result through the thread (10b plus the existing record-store tests); NOT_AN_INCIDENT and AMBIGUOUS from the awaited command check (existing comms tests).
- Concurrency/cancellation: no new behaviour. A cancelled await leaves at most one in-flight RecordStore call, bounded by botocore's per-attempt timeout and retries (integrations/aws/settings.py:86). This is documented in the adapter docstring, with no test, since it is the to_thread contract.

Size estimate (production, tests excluded): core/store.py ~90 (14 Protocol signatures, 2 renames, 2 adapters with 14 forwards), core/adapters/in_memory.py ~25, core/api.py ~3, comms/service/draft.py ~30, form.py ~5, approval.py ~5, publication.py ~10, history.py ~4, comms/entrypoints/slack.py ~6, scribe/service.py ~1. That is ~180 LOC in 10 production files, plus 2 decisions and the README. It is one subsystem (incident feature) and a purely mechanical signature change, so it is within the gate. Tests: ~51 files changed mechanically, plus 2 new.

Assumptions and doubts (each with its check):
- A1: No production caller outside features/incident calls these stores or find_incident_for_conversation (response/legacy_upgrade_job.py uses RecordStore directly; modules/ hits are name substrings). Check: rg for the 14 method names on store-typed receivers and for find_incident_for_conversation repo-wide at implementation, including jobs/ and server/.
- A2: No async caller exists in L3 that I have not listed. L3 adds no comms/scribe callers, and its new methods have no production caller until L6a. Check: rg the three new method names after the sync.
- A3: The sync Bolt handlers run with no running event loop (a Bolt worker thread), so asyncio.run is safe; the same file already does it six times. Check: the entrypoint and dispatch tests.
- A4: RecordStore (boto3 client) is safe to call from worker threads. boto3 clients are thread-safe (outbound-clients.md Threads). Check: the RecordStore provider shares a client, not a resource or session, per call. Read its factory at implementation.
- A5: The L3 sync onto main 0e12a616 is clean (L3 touches core/store.py, in_memory.py and api.py; L4a/L4b touched api.py, in_memory.py and the report/VideoCall parts). Check: the human's gh stack sync output; any conflict is resolved on L3, never from L3b.
- A6: mypy covers app/tests, so a missed await in a test is a type error. Check: the full mypy run lists no unused-coroutine errors.

Blast radius and rollback: the incident comms status-update modal (command, New update, History, Save, Generate, Approve, Published) and scribe's draft command. A missed await shows up as a coroutine where an OperationResult is expected; mypy and the comms tests catch it before merge. No data, schema, config, IAM or terraform change, so no deploy-checks. One `git revert` restores the sync ports. Ordering: it stacks on L3. L3 (#1846) merges first; this layer merges after it, and L6a (145.8.3) stacks above it. L3c (145.8.8) branches from main after this merges.

Domain-model evolution: not applicable. No entity, field or cardinality changes; only method colour changes.

Legacy surfaces: no pin or cutover. The legacy_surface updates-command test is only exercised, not rewired, and there is no seam-baseline change.

Not in scope: IncidentReport and IncidentTranscriptReader (TASK-145.8.8), TimelineStore (TASK-145.9.x when it gains an async consumer), RecordStore itself (TASK-25), and async Bolt (TASK-33).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: implemented on stack-l/task-145.8.7-async-ports (above L3 75843cfd). Production (10 files, ~180 LOC): store.py Protocols async; the sync bodies became private _RecordIncidentStoreCalls/_RecordStatusUpdateStoreCalls and RecordIncidentStore/RecordStatusUpdateStore forward each method through one asyncio.to_thread; in_memory.py fakes async (bind/seed/entries and the TimelineStore stay sync); api.find_incident_for_conversation async; comms start/save draft, start form, overview, _read_approved, _security_gate, _append, _append_new async; asyncio.run added in the three sync Bolt handlers (status-update command, New update, History); scribe awaits the command check. Decisions: outbound-clients.md Migration names TASK-145.8.8 for report+reader and a Changes line; transport-slack.md tolerance moves to TASK-145.8.8; README core row. Tests: 2 new offload files (thread id per RecordStore request, contextvars visible in the thread, classified failure), api_surface asserts all 14 methods on Protocol/adapter/fake and the command check are coroutines; ~51 test files converted mechanically (sync Bolt-driving tests stay sync, using asyncio.run or AsyncMock stubs). Plan assumption A6 was wrong: [tool.mypy] excludes ^tests/, so missed awaits in tests were found with a temp config and pytest -W error::RuntimeWarning instead; the pre-existing test-only mypy errors under that config (69 in 6 files, unchanged counts) are not part of any gate. Gates (from app/): ruff check . All checks passed; lint-imports Contracts: 13 kept, 0 broken; make check-package-shape OK (3 baselined); make check-test-seams OK (12 baselined); mypy Found 40 errors in 13 files (same as the L4b baseline 40/13, none in touched files); pytest tests --ignore=tests/smoke 7236 passed; incident tests with -W error::RuntimeWarning 2496 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T22:11:00Z

---

2026-11-10 (human): plan APPROVED as written (stores-only scope after the size-gate split; report and reader in TASK-145.8.8). Implementation on stack-l/task-145.8.7-async-ports above L3 75843cfd.

---
<!-- COMMENTS:END -->
