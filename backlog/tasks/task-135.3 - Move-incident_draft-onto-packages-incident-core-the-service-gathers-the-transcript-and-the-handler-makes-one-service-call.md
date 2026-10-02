---
id: TASK-135.3
title: >-
  Move incident_draft onto packages/incident/core: the service gathers the
  transcript and the handler makes one service call
status: To Do
assignee: []
created_date: '2026-10-02 15:39'
updated_date: '2026-10-02 15:43'
labels:
  - plugin-architecture
  - features
  - slack
milestone: m-7
dependencies:
  - TASK-135.1
references:
  - decisions/feature-packages.md
  - decisions/platform-transports.md
parent_task_id: TASK-135
priority: medium
type: task
ordinal: 304000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-135 (migrate). Behaviour-preserving refactor of packages/incident_draft onto the IncidentTranscriptReader interface added by TASK-135.1.

TODAY (verified 2026-10-02 at c8de7643)
- packages/incident_draft/service.py defines IncidentChannelPort (:222) with five methods returning raw Slack payloads; domain.py defines its own TranscriptMessage (:16) with a pre-formatted timestamp string; adapters/slack.py holds SlackIncidentChannel and providers.py holds get_incident_channel_port (:22).
- platforms/slack.py (478 lines) gathers the inputs before calling the service: _find_incident_document_id (:264), _fetch_transcript (:291), _resolve_self_identity (:345), _is_own_message (:369), _is_channel_event (:383), _normalize_name (:389), _format_time (:394), _resolve_display_name (:414), _resolve_limit (:436), _resolve_channel_start (:449). The handler calls draft_incident_document(document_id, messages) at :164, after posting a progress notice at :157.
- Draft filters the bot's own posts and Slack system events, and stamps each message with its time in the configured zone.

THIS SLICE
- The service gains the use-case function the handler calls: it finds the report document, signals that work has started, resolves the limit and the start of the window, reads the filtered transcript through packages.incident.core.api and calls draft_incident_document, whose signature is unchanged.
- The handler keeps argument parsing (--limit), the progress notice, one service call and rendering.
- IncidentChannelPort, the package's TranscriptMessage and get_incident_channel_port are deleted. What remains of the channel lookups is the 'Incident report' bookmark, behind a draft-only interface, IncidentReportLinkLookup, with its Slack adapter and provider get_incident_report_link_lookup.
- The test-side names TASK-136 left to TASK-135 go with them (test_incident_draft_slack.py: _CHANNEL_PORT, mock_port, the 'fake incident channel port' docstring) and the legacy_surface conftest patch of get_incident_channel_port for this package.

Human decisions 2026-10-02: the report lookup stays in this package and out of core/, because channel-to-report resolution belongs to the TASK-97 packet; it is named IncidentReportLinkLookup. The feature-independence contract gets one temporary ignore entry for this package's import of packages.incident.core.api, removed by TASK-135.4.

Independent of TASK-135.2: the two can be done in either order or in parallel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /sre incident draft is handled with one service call; the service finds the report document and reads the transcript through packages.incident.core.api, and platforms/slack.py holds no bookmark lookup, history fetch, name resolution, message filtering or time formatting
- [ ] #2 packages/incident_draft defines no channel interface and no TranscriptMessage of its own; its only Slack lookup is IncidentReportLinkLookup, which returns plain strings and is resolved by get_incident_report_link_lookup
- [ ] #3 The progress notice is still posted only after the report document is found and before the transcript is read; a channel with no bookmarked report gets the unchanged no-document reply and no notice
- [ ] #4 rg -n 'Port\b|_port\b|_PORT\b|\bport\b' over packages/incident_draft and tests/unit/packages/incident_draft finds nothing, and the legacy_surface conftest no longer patches get_incident_channel_port
- [ ] #5 Command name, arguments and replies are unchanged: the legacy_surface suite is green with no assertion change, and the transcript sent to the model keeps the same lines, filtering and time stamps
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; exactly one import-linter ignore entry is added (packages.incident_draft.service -> packages.incident.core.api), marked as removed by TASK-135.4
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Size: 8 production files in one package plus app/pyproject.toml; about 450 changed production LOC, of which about 300 are deletions of handler code whose replacement was reviewed in TASK-135.1. At the edge of the gate and not divisible further without leaving the handler half-migrated. Refactor only, no behaviour change.

DESIGN (decided)
- draft_incident_document(document_id, messages, *, documents, summarizer) keeps its name and signature. The legacy_surface suite stubs it and asserts its two positional arguments (test_slack_command_registration_surface.py:320-326, :340-345); gathering goes into a new function above it.
- New service function, the handler's one call:
  draft_incident_document_from_conversation(conversation_id: str, *, limit: int | None = None, on_started: Callable[[], None] | None = None, reader: IncidentTranscriptReader | None = None, report_links: IncidentReportLinkLookup | None = None) -> OperationResult[DraftedDocument]
  Order, kept from handle_draft_command (:145-164): find the document id; none -> permanent error with the new NO_DOCUMENT_CODE; call on_started; resolve the limit and the window start (the conversation's start, else now minus DEFAULT_SINCE_HOURS); reader.read_transcript(..., exclude_own_and_system_messages=True); return await draft_incident_document(document_id, messages), both positional.
- on_started is how the handler's progress notice keeps its place (after the document is found, before the slow work) while the handler still makes one service call.
- IncidentReportLinkLookup (service.py), runtime_checkable Protocol, one method: find_report_links(conversation_id: str) -> Sequence[str], the links of the conversation's 'Incident report' bookmarks in listed order, empty on a platform failure. The service extracts the Google Docs id with _DOC_ID_PATTERN, as the handler does today. Draft-only; not in core/ (TASK-97 owns report resolution).
- TranscriptMessage comes from packages.incident.core.api and carries posted_at. The service formats it for the model: _format_time moves from the handler and takes the datetime, with the same '%Y-%m-%d %H:%M %Z' output in settings.TIMEZONE, UTC fallback for an unknown zone and no stamp for None.
- service.py is the only module of the package that imports core.

STEPS
1. Tests first (red):
   - New app/tests/unit/packages/incident_draft/test_incident_draft_conversation_draft.py: draft_incident_document_from_conversation against Protocol fakes of IncidentTranscriptReader and IncidentReportLinkLookup and a patched draft_incident_document.
   - app/tests/unit/packages/incident_draft/test_incident_draft_slack.py, edited in place:
     - remove _CHANNEL_PORT (:31), mock_port (:77, :82) and the fake-channel helper with its 'fake incident channel port' docstring (:36-37); :70 asserts handle_draft_command(payload, {}, provider.reply);
     - TestHandleDraftCommand stubs draft_incident_document_from_conversation; :121 renders the NO_DOCUMENT result; :177 asserts the limit passed to the service; :106 is deleted (ordering is pinned on the core adapter);
     - TestFindIncidentDocumentId (:187-201), the limit test (:218) and TestTimestampFormatting (:398-421) move to the service tests; the two fetch tests in TestHelpers (:204, :212), TestBotMessageFiltering (:232-269) and TestBotDetectionSignals (:271-318) are deleted, each behaviour being pinned on the core adapter by TASK-135.1;
     - TestProgressNotice (:320-365): the notice content and failed-notice tests stay on the handler, driven through the on_started callback it passes; 'precedes the transcript fetch' (:338) and 'no notice without a document' (:349) move to the service test as assertions on when on_started is called;
     - TestPartialDraftMessage is untouched.
   - app/tests/unit/packages/incident_draft/test_incident_draft_service.py, in place: TranscriptMessage built with posted_at datetimes (11 lines); add the time-formatting cases moved from the handler tests.
   - app/tests/unit/packages/incident_draft/test_incident_draft_slack_adapter_lookup.py, in place: keep the bookmark test (:15) rewritten to find_report_links and the builder test (:100); delete the history, channel, user and self-identity tests (:25-66); the propagate-errors test (:91) becomes 'a Slack API error yields no links'; the isinstance check (:108) targets IncidentReportLinkLookup.
2. app/packages/incident_draft/service.py: delete IncidentChannelPort (:221-243); add NO_DOCUMENT_CODE, IncidentReportLinkLookup and draft_incident_document_from_conversation with the helpers moved from the handler (_DOC_ID_PATTERN, document-id extraction with its incident_draft_bookmark_link_invalid warning, _resolve_limit, window start, _format_time); _transcript_line (:464-468) formats message.posted_at; TranscriptMessage is imported from packages.incident.core.api instead of domain (:28-36). The link lookup's provider is imported inside the function, as get_incident_document_store is today (:281), because providers.py imports this module.
3. app/packages/incident_draft/platforms/slack.py: handle_draft_command(payload, parsed_args, reply) drops the channel parameter and makes the one call asyncio.run(draft_incident_document_from_conversation(..., on_started=...)); _dispatch and _dispatch_default (:82-86) stop resolving a provider; _render_error (:226-261) maps NO_DOCUMENT_CODE to the existing no_document message and key (:147-152); delete _find_incident_document_id (:264-288), _fetch_transcript (:291-342), _resolve_self_identity (:345-366), _is_own_message (:369-380), _is_channel_event (:383-386), _normalize_name (:389-391), _format_time (:394-411), _resolve_display_name (:414-433), _resolve_limit (:436-446), _resolve_channel_start (:449-468), _SYSTEM_SUBTYPES (:52-67), _DOC_ID_PATTERN and _INCIDENT_REPORT_BOOKMARK (:49-50); module and handler docstrings (:12-15, :117-128) describe the new flow. _notify_working, _success_response and the registration call are unchanged.
4. app/packages/incident_draft/adapters/slack.py: SlackIncidentChannel becomes SlackIncidentReportLinkLookup with find_report_links (bookmarks_list, the 'Incident report' title filter, warning incident_draft_bookmarks_fetch_failed and an empty result on an API error); build_incident_channel becomes build_incident_report_link_lookup; the other four methods are deleted.
5. app/packages/incident_draft/providers.py: get_incident_channel_port (:21-24) becomes get_incident_report_link_lookup returning IncidentReportLinkLookup; imports and the module docstring follow.
6. app/packages/incident_draft/domain.py: delete TranscriptMessage (:16-27) and the 'from __future__ import annotations' line (:7), which is deprecated on 3.14 and sits in a touched file.
7. app/packages/incident_draft/__init__.py: drop the TranscriptMessage re-export (:17, :56).
8. app/packages/incident_draft/README.md: the flow section says the service finds the report and reads the transcript through packages/incident/core; wording says 'interface'.
9. app/pyproject.toml, feature-independence ignore_imports (:361-368): add "packages.incident_draft.service -> packages.incident.core.api" under a comment 'Temporary (TASK-135.3): removed by TASK-135.4 when the package moves into the incident umbrella'.
10. app/tests/integration/legacy_surface/:
   - conftest.py: replace the IncidentDraftSlackChannel import (:39) and the get_incident_channel_port patch (:186) with two patches over the same fake client: get_incident_transcript_reader on the packages.incident_draft.service module, and get_incident_report_link_lookup on packages.incident_draft.providers. Drop the incident_draft_slack import (:40) if nothing else uses it.
   - test_slack_command_registration_surface.py: the stub target for draft_incident_document moves from the handler module to the service module (import :22; setattr :320, :340). No assert line changes.
   - INVENTORY.md:115: refresh the path:line reference if the registration line moved.
11. Gates from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files) ; uv run lint-imports ; uv run pytest tests --ignore=tests/smoke. Then rg -n 'Port\b|_port\b|_PORT\b|\bport\b' app/packages/incident_draft app/tests/unit/packages/incident_draft (expect nothing) and rg -n 'get_incident_channel_port' app (expect nothing once TASK-135.2 has also merged).

AC MAP
- #1 -> steps 2, 3; test_incident_draft_conversation_draft.py and TestHandleDraftCommand.
- #2 -> steps 2, 4, 5, 6, 7; the adapter lookup test and lint-imports.
- #3 -> steps 2, 3; the on_started ordering tests in test_incident_draft_conversation_draft.py, TestProgressNotice, and legacy_surface test_incident_draft_without_bookmarked_document_does_not_draft.
- #4 -> steps 1, 10, 11 (the two rg commands, output recorded in notes).
- #5 -> step 10; pytest tests/integration/legacy_surface recorded before and after; the service tests assert filtering is requested and that a transcript line renders as '[YYYY-MM-DD HH:MM ZZZ] Name: text'.
- #6 -> steps 9, 11.

TEST MATRIX (test_incident_draft_conversation_draft.py unless noted)
- Happy: first 'Incident report' link with a document id is used; on_started is called once, after the lookup and before read_transcript; read_transcript gets the conversation's start, the resolved limit and filtering on; draft_incident_document receives (document_id, messages).
- Boundary: no links, or only links without a document id (warning logged) -> NO_DOCUMENT, on_started and read_transcript never called; an invalid link followed by a valid one -> the valid one; limit None, 0, negative and above the cap; conversation_started_at None -> now minus DEFAULT_SINCE_HOURS; on_started omitted.
- Failure: reader returns an empty sequence -> EMPTY_HISTORY from draft_incident_document; its error result is returned unchanged.
- Time formatting (test_incident_draft_service.py): date, time and zone abbreviation; daylight-saving change; unknown zone falls back to UTC; posted_at None gives a line without a stamp.
- Adapter (test_incident_draft_slack_adapter_lookup.py): title filter, order kept, missing link gives an empty string entry, API error gives no links.
- Handler (test_incident_draft_slack.py): success and partial replies, each known error code including NO_DOCUMENT, generic error, missing channel id, --limit translation, the notice text and a failed notice not failing the command.

ASSUMPTIONS AND HOW TO VERIFY
- Only _transcript_line reads the message time in service.py (rg '\.timestamp' found :466-467 only on 2026-10-02); adapters/google_docs.py does not use TranscriptMessage. Re-run rg 'TranscriptMessage' app/packages/incident_draft before deleting the type.
- Only tests import packages.incident_draft.TranscriptMessage, get_incident_channel_port or SlackIncidentChannel (rg on 2026-10-02: tests, the legacy_surface harness and pyproject).
- A timestamp formatted from the UTC datetime the reader returns equals today's formatting from the Slack ts float: both go through datetime.fromtimestamp(float(ts), tz=UTC). The moved TestTimestampFormatting cases pin it.
- import-linter's independence contract follows indirect imports, so the ignored edge must be the package's only import of packages.incident; lint-imports confirms.
- on_started runs inside the coroutine and posts through the synchronous reply interface, like the reader call; no other task shares that loop. Non-blocking handlers belong with TASK-33.

BLAST RADIUS AND ROLLBACK
- Only /sre incident draft. Replies, arguments, the progress notice's timing and the model input are unchanged. Log events for transcript gathering change name (incident_draft_history_fetched, _history_fetch_failed, _self_identity, _auth_test_failed, _user_lookup_failed and _channel_info_failed become the core adapter's incident_transcript_* events); nothing outside app/ references the old names (rg over the repo, 2026-10-02).
- No configuration, manifest or schema change; INCIDENT_DRAFT__* variables are untouched. A single git revert restores the previous code.
<!-- SECTION:PLAN:END -->
