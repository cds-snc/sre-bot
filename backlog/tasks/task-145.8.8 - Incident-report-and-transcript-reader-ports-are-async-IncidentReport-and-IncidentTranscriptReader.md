---
id: TASK-145.8.8
title: >-
  Incident report and transcript reader ports are async: IncidentReport and
  IncidentTranscriptReader
status: Done
assignee: []
created_date: '2026-11-10T21:44:00Z'
updated_date: '2026-11-16T23:11:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.8.7
references:
  - decisions/outbound-clients.md
  - decisions/transport-slack.md
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
ordinal: 521500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L row L3c, a side PR from main after TASK-145.8.7 (L3b) merges; split from TASK-145.8.7 at its full planning (size gate, human 2026-11-10). Applies the async-port rule (decisions/outbound-clients.md) to the two remaining incident ports: IncidentReport (GoogleDocsIncidentReport offloads its googleapiclient calls inside its own methods with asyncio.to_thread; link stays sync, it is pure) and IncidentTranscriptReader (SlackIncidentTranscriptReader moves to the async Slack client from get_async_slack_web_client, no thread). The in-memory report fake and the test-local fake readers become async; callers in scribe/service.py (draft and summarize, the _resolve_*_window_start helpers) and comms/service/draft.py (_read_window) await them. The comms start/save chain is already async after TASK-145.8.7, so no Bolt entrypoint changes here. Closes the transport-slack.md IncidentTranscriptReader tolerance and the outbound-clients.md Migration entry for these two ports.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IncidentReport (create_from_template, list_placements, replace_placeholders, read_sections, write_draft_copy) and IncidentTranscriptReader (conversation_started_at, read_transcript) are async def in core; link stays sync; GoogleDocsIncidentReport offloads its blocking calls with asyncio.to_thread inside its methods; SlackIncidentTranscriptReader uses AsyncWebClient; InMemoryIncidentReport is async; no caller wraps a port call in to_thread
- [x] #2 scribe/service.py and comms/service/draft.py await the two ports; behaviour tests unchanged apart from awaiting and async fakes
- [x] #3 transport-slack.md drops the IncidentTranscriptReader tolerance; outbound-clients.md Migration drops IncidentReport and IncidentTranscriptReader from its sync-port list
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-16 against main ac3b8f8d (L3b #1852 merged). Side PR, branch task-145.8.8-report-reader-async from an up-to-date main. Behaviour unchanged: only the colour of two ports and their callers. Rules carried in: outbound-clients.md async-port rule (TASK-145.7.6 R1: ports consumed from async code are async def; adapters offload blocking SDKs with asyncio.to_thread inside their own methods; callers never do); 145.8.7 asyncio.run-at-the-edge (every scribe and comms caller is already async and its Bolt handler already runs it with one asyncio.run, so no entrypoint changes); closes the outbound-clients.md Migration entry "sync ports with async consumers" for these two ports and the transport-slack.md tolerance; set_status_text is already async (TASK-145.8.4, #1859, open).

Call sites (production, main ac3b8f8d)
- core/api.py:144-170 IncidentTranscriptReader (conversation_started_at :153, read_transcript :161); :278-330 IncidentReport (list_placements :288, create_from_template :297, replace_placeholders :308, read_sections :315, write_draft_copy :319; link stays sync); get_incident_report :389, get_incident_transcript_reader :464 (lru_cache) unchanged.
- core/adapters/google_docs.py:626-760 GoogleDocsIncidentReport: blocking helpers _list_all (:643), _copy_template (:686), _replace_all_text (:705), read_document_sections (:720), write_draft_document (:741). Module functions stay sync (legacy modules/incident/incident_document.py:15,52,79 call replace_placeholders the module function, not the class).
- core/adapters/slack.py:74-270 SlackIncidentTranscriptReader on WebClient: conversations_info (:89), conversations_history (_read_history ~:187), conversations_replies (_read_thread_replies ~:223), auth_test (_resolve_self_identity ~:245), users_info (_resolve_display_name ~:265); build_incident_transcript_reader :282 uses get_slack_web_client; module docstring :1-20 says sync.
- core/adapters/in_memory.py:344-460 InMemoryIncidentReport (five methods).
- scribe/service.py: draft_incident_document_from_conversation :286 read_transcript, :288 _resolve_draft_window_start; draft_incident_document :333 read_sections, :411 write_draft_copy; _resolve_draft_window_start :549-563; summarize_incident_conversation :937 read_transcript; _resolve_summary_window_start :1014-1031. All public callers already async def.
- comms/service/draft.py: _read_window :442-477 (sync today) called from start_status_update_draft :134 and generate_status_update_draft :316 (both async def).
- No caller offloads today: rg "to_thread" over scribe/ and comms/ returns nothing (verify again at the end).

Steps (TDD: tests first per step, then code)
S1 Tests: test_incident_core_api_surface.py: one parametrized test that every IncidentReport method except link, and both IncidentTranscriptReader methods, is a coroutine function on the Protocol, GoogleDocsIncidentReport, InMemoryIncidentReport and SlackIncidentTranscriptReader; link is not (fails first). New test_incident_core_report_offload.py: each GoogleDocsIncidentReport method with a monkeypatched blocking helper records threading.get_ident() and asserts it differs from the loop thread, and that the helper ran once (one to_thread per call). (AC #1)
S2 core/api.py: the five IncidentReport methods and the two IncidentTranscriptReader methods become async def; docstrings say awaited, adapters offload. (~10 LOC) (AC #1)
S3 core/adapters/google_docs.py: each method async def; settings/system checks stay on the loop; the one blocking helper call becomes `await asyncio.to_thread(helper, ...)` (the #1859 set_status_text shape). (~15 LOC) (AC #1)
S4 core/adapters/in_memory.py: InMemoryIncidentReport's five methods async def, bodies unchanged. (~5 LOC) (AC #1)
S5 core/adapters/slack.py: SlackIncidentTranscriptReader takes AsyncWebClient; public methods and the private _read_history, _read_thread_replies, _resolve_self_identity, _resolve_display_name become async and await each call; thread pages stay sequential (no gather: behaviour and rate-limit shape unchanged). build_incident_transcript_reader uses get_async_slack_web_client(). Module docstring: both adapters on the async clients. (~30 LOC) (AC #1)
S6 scribe/service.py: await read_transcript, read_sections, write_draft_copy; _resolve_draft_window_start and _resolve_summary_window_start become async and are awaited. comms/service/draft.py: _read_window async, awaited at :134 and :316. (~15 LOC) (AC #2)
S7 Tests moved to awaiting (no assertion changes): core test_incident_core_transcript_read.py and test_incident_core_conversation_started_at.py (MagicMock(spec=WebClient) -> AsyncMock(spec=AsyncWebClient), as core/conftest.py:53 already does), test_incident_core_report_protocol_parity.py, _report_placements.py, _report_create.py, _report_no_delegation.py, and the class-level tests in _google_docs_placeholders.py and _google_docs_sections.py; scribe test_incident_scribe_conversation_draft.py, _conversation_summarize.py, _draft_service.py (_StubIncidentReport async), _draft_report_default.py; comms fake readers in test_incident_comms_status_update_*.py and the integration dispatch test. legacy_surface/conftest.py:181-193: the seam builds the reader over a small async view of FakeSlackClient (each attribute an async def delegating to the sync fake, so calls_to still records); the seam baseline line (bin/baselines/test_seams_legacy.txt:19) is unchanged, its target is the same. (AC #2)
S8 Docs: decisions/outbound-clients.md Migration drops IncidentReport and IncidentTranscriptReader from "sync ports with async consumers" (the RecordStore/providers and oncall_sync parts stay) plus a 2026-11-16 history line; decisions/transport-slack.md:73 tolerance line deleted plus a history line; features/incident/README.md core row and scribe/README.md interface lines say async. (AC #3)
S9 Gates (AC #4): ruff, targeted tests per step; at the end once, sequential: mypy (baseline 40/13), pytest tests --ignore=tests/smoke; lint-imports, make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams; rg "to_thread" features/incident/scribe features/incident/comms is empty.

AC traceability
#1 -> S1-S5, tests: api_surface coroutine test, report_offload, transcript_read, conversation_started_at, report parity. #2 -> S6-S7, tests: scribe and comms suites unchanged apart from awaiting. #3 -> S8, evidence: diff of the two ADRs. #4 -> S9, evidence: command output.

Test matrix
Happy: transcript read, thread expansion, own/system filter, started_at (existing cases, awaited); report parity suite on both implementations. Boundary: started_at with no created; limit trimming; empty placements folder. Failure: SlackApiError on first page classified, later page logged and kept (existing); Docs 403/404/429 classified (existing); non-Slack / non-Google references UNSUPPORTED_OPERATION before any call, now asserted without awaiting the client. Off-loop: report_offload per method.

Size: 6 production files ~80 LOC + 2 ADRs + 2 READMEs; ~18 test files, mechanical. One subsystem (incident). Gate passes; mechanical colour change, no behaviour change.

Assumptions (verified)
- A process-wide AsyncWebClient is safe across the per-handler asyncio.run loops: slack_sdk 3.45 async_internal_utils._request_with_session opens a ClientSession per request and closes it when none is injected (read 2026-11-16); IncidentConversation already relies on this since TASK-145.6.3.
- Every caller is async and already under asyncio.run at its Bolt edge (scribe/entrypoints/slack.py:187,248; comms entrypoints via start/generate).
- Legacy modules call google_docs module functions only; they stay sync.

Blast radius and rollback
Merging deploys: /sre incident draft, summarize and the comms status-update draft read Slack on the async client and the report through to_thread. Wrong behaviour would show as a failed draft/summary reply, no data written wrongly. One git revert restores it; no config, terraform or data changes.

Merge order with #1859 (TASK-145.8.4, open): both edit core/api.py IncidentReport, google_docs.py, in_memory.py and the outbound-clients.md Migration line. Textual only; whichever merges second rebases (if this merges first, #1859 drops its "(all but set_status_text)" parenthetical, the entry being gone).

Domain-model evolution: not applicable (no entity or record shape change; port colour only).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16: plan approved by the human, OQ1-OQ4 as recommended (one to_thread per GoogleDocsIncidentReport method around its helper; thread pages sequential; legacy seam over an async view of FakeSlackClient; this PR may merge before #1859).

2026-11-16 implemented (S1-S9), branch task-145.8.8-report-reader-async from main ac3b8f8d.
- Ports: core/api.py IncidentReport (all but link) and IncidentTranscriptReader are async def. GoogleDocsIncidentReport awaits asyncio.to_thread(helper, ...) once per method (checks and settings stay on the loop; module functions stay sync for legacy modules/incident). SlackIncidentTranscriptReader takes AsyncWebClient (build_incident_transcript_reader uses get_async_slack_web_client), pages and threads awaited sequentially. InMemoryIncidentReport async.
- Callers: scribe/service.py awaits read_transcript, read_sections, write_draft_copy; _resolve_draft_window_start and _resolve_summary_window_start async. comms/service/draft.py _read_window async. rg to_thread over scribe/ and comms/: none.
- Tests: new test_incident_core_report_offload.py (each GoogleDocsIncidentReport method builds its Docs/Drive service off the loop thread; fakes at the integrations factory edge); api_surface asserts coroutine methods (link sync). Core, scribe, comms and the comms dispatch test moved to async fakes / AsyncMock(spec=AsyncWebClient), assertions unchanged. legacy_surface/conftest.py: legacy_scribe_transcript_reader_seam builds the reader over _AwaitedSlackClient (async view of FakeSlackClient); fixture, target and baseline entry unchanged.
- Docs: outbound-clients.md Migration drops the two ports + history line; transport-slack.md tolerance removed + history line; features/incident/README.md core row says async.
- Gates: ruff check . all passed; ruff format clean; lint-imports 13 kept 0 broken; check-settings-key-ownership OK; check-test-seams OK (47 strict, 12 legacy baselined); mypy 40 errors in 13 files (= baseline, none in touched files); pytest tests --ignore=tests/smoke: 7370 passed, 1 failed (test_bin_package_shape_check::test_the_repository_tree_matches_its_baseline). That failure and make check-package-shape both name only capabilities/oncall:readme-missing: an untracked directory of __pycache__ left in the worktree from the task-146.1.1 branch, not part of this change. AC #4 stays open until the human removes it and package-shape is rerun.
- Merge order: textual overlap with #1859 (api.py, google_docs.py, in_memory.py, outbound-clients.md Migration line, features/incident/README.md core row); the second to merge rebases.
<!-- SECTION:NOTES:END -->
