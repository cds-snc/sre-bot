---
id: TASK-135.2
title: >-
  Move incident_summary onto packages/incident/core: the service gathers the
  transcript and the handler makes one service call
status: Done
assignee: []
created_date: '2026-10-02 15:39'
updated_date: '2026-10-08 15:43'
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
ordinal: 303000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-135 (migrate). Behaviour-preserving refactor of packages/incident_summary onto the IncidentTranscriptReader interface added by TASK-135.1.

TODAY (verified 2026-10-02 at c8de7643)
- packages/incident_summary/service.py defines its own TranscriptMessage (:39) and IncidentChannelPort (:48); adapters/slack.py holds SlackIncidentChannel and providers.py holds get_incident_channel_port.
- platforms/slack.py (349 lines) gathers the inputs before calling the service: _fetch_transcript (:165), _resolve_display_name (:204), _resolve_limit (:226), _resolve_oldest (:239), _resolve_channel_start (:251). The handler calls summarize_transcript(messages, instructions=...) at :142.
- Summarize does not filter the bot's own or system messages and carries no message times.

THIS SLICE
- The service gains the use-case function the handler calls: it resolves the limit and the start of the window, reads the transcript through packages.incident.core.api and calls summarize_transcript, whose signature is unchanged.
- The handler keeps argument parsing (--since, --limit), one service call and rendering.
- The package's IncidentChannelPort, TranscriptMessage, SlackIncidentChannel and get_incident_channel_port are deleted, with their tests rewritten or removed.
- The test-side names TASK-136 left to TASK-135 go with them (test_incident_summary_slack.py: _CHANNEL_PORT, mock_port, test_handler_dispatches_with_channel_port_and_parsed_args, the 'fake incident channel port' docstring) and the legacy_surface conftest patch of get_incident_channel_port for this package. Prose that said 'port' (service.py, README.md, platforms/slack.py) says 'interface'.

Human decisions 2026-10-02: summarize keeps reading unfiltered messages (behaviour preserved; whether it should filter is a separate product question). The feature-independence contract gets one temporary ignore entry for this package's import of packages.incident.core.api, removed by TASK-135.4.

Independent of TASK-135.3: the two can be done in either order or in parallel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 /sre incident summarize is handled with one service call; the service reads the transcript through packages.incident.core.api, and platforms/slack.py holds no history fetch, name resolution or window resolution
- [x] #2 packages/incident_summary defines no channel interface, TranscriptMessage, Slack adapter or provider function of its own; adapters/ and providers.py are deleted
- [x] #3 rg -n 'Port\b|_port\b|_PORT\b|\bport\b' over packages/incident_summary and tests/unit/packages/incident_summary finds nothing, and the legacy_surface conftest no longer patches get_incident_channel_port for incident_summary
- [x] #4 Command name, arguments and replies are unchanged: the legacy_surface suite is green with no assertion change, and summarize still sends unfiltered messages without times to the model
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; exactly one import-linter ignore entry is added (packages.incident_summary.service -> packages.incident.core.api), marked as removed by TASK-135.4
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Size: 8 production files (3 deleted) in one package plus app/pyproject.toml; about 280 changed production LOC, most of it deletion. Inside the gate. Refactor only, no behaviour change.

DESIGN (decided)
- summarize_transcript(messages, *, instructions, summarizer) keeps its name and signature. The legacy_surface suite stubs it and asserts it receives the transcript as its one positional argument (test_slack_command_registration_surface.py:353-360, :374); that seam must survive, so gathering goes into a new function above it instead of into it.
- New service function, the handler's one call:
  summarize_incident_conversation(conversation_id: str, *, since: timedelta | None = None, limit: int | None = None, instructions: str | None = None, reader: IncidentTranscriptReader | None = None) -> OperationResult[str]
  It resolves the limit (None or <= 0 -> DEFAULT_HISTORY_LIMIT, else capped at MAX_HISTORY_LIMIT), resolves the window start (now minus since; else reader.conversation_started_at(); else now minus DEFAULT_SINCE_HOURS), calls reader.read_transcript(conversation_id, since=start, limit=limit) with filtering off, and returns await summarize_transcript(messages, instructions=instructions) with messages passed positionally.
- reader defaults to get_incident_transcript_reader(), imported into service.py from packages.incident.core.api. service.py is the only module of the package that imports core.
- The handler keeps what is platform input translation: --since text to a timedelta (_parse_since_seconds stays) and --limit to int | None.

STEPS
1. Tests first (red):
   - New app/tests/unit/packages/incident_summary/test_incident_summary_conversation_summarize.py: summarize_incident_conversation against a Protocol fake of IncidentTranscriptReader and a patched summarize_transcript.
   - app/tests/unit/packages/incident_summary/test_incident_summary_slack.py, edited in place:
     - remove _CHANNEL_PORT (:27), mock_port (:59, :62, :71, :74) and the fake-channel helper with its 'fake incident channel port' docstring (:31-32);
     - rename test_handler_dispatches_with_channel_port_and_parsed_args (:52) to test_handler_dispatches_with_parsed_args; it and :64 assert handle_summarize_command(payload, parsed_args);
     - TestHandleSummarizeCommand stubs summarize_incident_conversation; :152, :167, :180 and :192 assert the limit, since and instructions the handler passes; :202, :220 and :237 are deleted (same behaviours are pinned on the core adapter by TASK-135.1);
     - TestArgumentParsingHelpers keeps the three _parse_since_seconds tests; :270, :274 and :281 move to the new service test file;
     - TestResolveDisplayName (:297-338) and TestFetchTranscript (:408-427) are deleted (core adapter tests cover them); TestResolveChannelStart (:375-406) moves to the new service test file; TestToSlackMrkdwn is untouched.
   - app/tests/unit/packages/incident_summary/test_incident_summary_service.py: TranscriptMessage imported from packages.incident.core.api.
   - Delete app/tests/unit/packages/incident_summary/test_incident_summary_slack_adapter_lookup.py with the adapter.
2. app/packages/incident_summary/service.py: delete TranscriptMessage (:39-45) and IncidentChannelPort (:47-61); import IncidentTranscriptReader, TranscriptMessage and get_incident_transcript_reader from packages.incident.core.api; add summarize_incident_conversation with _resolve_limit and the window-start helper moved from the handler; 'port' in the module docstring (:4) and the summarize_transcript docstring (:76-77) becomes 'interface'.
3. app/packages/incident_summary/platforms/slack.py: handle_summarize_command(payload, parsed_args) drops the channel parameter and makes the one call asyncio.run(summarize_incident_conversation(...)); _dispatch and _dispatch_default (:64-68) stop resolving a provider; delete _fetch_transcript (:165-201), _resolve_display_name (:204-223), _resolve_limit (:226-236), _resolve_oldest (:239-248) and _resolve_channel_start (:251-270); module and handler docstrings (:9-10, :105, :114) describe the new flow and say 'interface'. Rendering, _to_slack_mrkdwn, _SLACK_FORMAT_INSTRUCTIONS and the registration call are unchanged.
4. Delete app/packages/incident_summary/providers.py, adapters/slack.py and adapters/__init__.py.
5. app/packages/incident_summary/__init__.py: drop the TranscriptMessage re-export (:14, :47); keep summarize_transcript.
6. app/packages/incident_summary/README.md: 'Summarizer port' (:9, :66) becomes 'interface'; the flow section says the service reads the transcript through packages/incident/core.
7. app/pyproject.toml, feature-independence ignore_imports (:361-368): add "packages.incident_summary.service -> packages.incident.core.api" under a comment 'Temporary (TASK-135.2): removed by TASK-135.4 when the package moves into the incident umbrella'.
8. app/tests/integration/legacy_surface/:
   - conftest.py: drop the IncidentSummarySlackChannel import (:41) and its patch (:187); patch get_incident_transcript_reader on the packages.incident_summary.service module with lambda: SlackIncidentTranscriptReader(client). Drop the incident_summary_slack import (:42) if nothing else uses it.
   - test_slack_command_registration_surface.py: the stub target for summarize_transcript moves from the handler module to the service module (import :23; setattr :353, :374). No assert line changes.
   - INVENTORY.md:116: refresh the path:line reference if the registration line moved.
9. Gates from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files) ; uv run lint-imports ; uv run pytest tests --ignore=tests/smoke. Then rg -n 'Port\b|_port\b|_PORT\b|\bport\b' app/packages/incident_summary app/tests/unit/packages/incident_summary (expect nothing) and rg -n 'incident_summary' app/tests/integration/legacy_surface/conftest.py (no get_incident_channel_port).

AC MAP
- #1 -> steps 2, 3; test_incident_summary_conversation_summarize.py and TestHandleSummarizeCommand.
- #2 -> steps 2, 4, 5; lint-imports plus the deleted-module check (the files no longer exist).
- #3 -> steps 1, 8, 9 (the two rg commands, output recorded in notes).
- #4 -> step 8; pytest tests/integration/legacy_surface recorded before and after; the service test asserts read_transcript is called with filtering off and that messages reach summarize_transcript unchanged.
- #5 -> steps 7, 9.

TEST MATRIX (test_incident_summary_conversation_summarize.py)
- Happy: since given -> read_transcript receives now minus since and conversation_started_at is not called; no since -> the conversation's start; the transcript and instructions reach summarize_transcript.
- Boundary: limit None, 0 and negative -> DEFAULT_HISTORY_LIMIT; above MAX_HISTORY_LIMIT -> capped; conversation_started_at returns None -> now minus DEFAULT_SINCE_HOURS.
- Failure: reader returns an empty sequence -> EMPTY_HISTORY from summarize_transcript; summarize_transcript's error result is returned unchanged.
- Handler (test_incident_summary_slack.py): success, empty-history notice, generic error, missing channel id without a service call, --since and --limit translation, invalid --since passed as None.

ASSUMPTIONS AND HOW TO VERIFY
- Only tests import packages.incident_summary.TranscriptMessage, providers or adapters: rg -n 'incident_summary' app --glob '!app/packages/incident_summary/**' on 2026-10-02 found only tests, the legacy_surface harness and pyproject. Re-run before deleting.
- import-linter's independence contract follows indirect imports, so the single ignored edge must be the package's only import of packages.incident: keep core imports out of platforms/slack.py and __init__.py; lint-imports confirms.
- The service calls the synchronous reader inside the coroutine the handler runs with asyncio.run. No other task shares that loop, and incident_draft's service already calls its synchronous document store the same way. Making it non-blocking belongs with TASK-33.
- The window start is computed from a clock in the service; tests patch that clock where they patched time.time on the handler module.

BLAST RADIUS AND ROLLBACK
- Only /sre incident summarize. Replies, arguments and the model input are unchanged. Log events for transcript gathering change name (incident_summary_history_fetched, _history_fetch_failed, _user_lookup_failed and _channel_info_failed become the core adapter's incident_transcript_* events); nothing outside app/ references the old names (rg over the repo, 2026-10-02).
- No configuration, manifest or schema change. A single git revert restores the previous code.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-02 as layer 2 of Stack G (handoff: doc-4), on branch stack-g/task-135.2-incident-summary-onto-core over layer 1 (0724af46). Stops at In Progress for human review.

Production changes (app/packages/incident_summary): service.py gains summarize_incident_conversation with _resolve_limit, _resolve_window_start and the _now clock, and loses TranscriptMessage and IncidentChannelPort (158 lines); platforms/slack.py makes the one service call and keeps _parse_since_seconds, the new input translators _parse_since and _parse_limit, rendering and registration (349 -> 246 lines); providers.py, adapters/slack.py and adapters/__init__.py deleted; __init__.py drops the TranscriptMessage re-export; README.md updated. app/pyproject.toml: one feature-independence ignore entry, 'packages.incident_summary.service -> packages.incident.core.api', under the comment 'Temporary (TASK-135.2): removed by TASK-135.4 ...'.

Tests: new test_incident_summary_conversation_summarize.py (16 tests over a Protocol fake of IncidentTranscriptReader); test_incident_summary_slack.py edited in place as planned (handler tests stub summarize_incident_conversation; _CHANNEL_PORT, mock_port and the fake-channel helper removed; test_handler_dispatches_with_parsed_args); test_incident_summary_service.py imports TranscriptMessage from packages.incident.core.api and drops its deprecated 'from __future__ import annotations' line; test_incident_summary_slack_adapter_lookup.py deleted with the adapter. TDD: red at collection (ImportError: summarize_incident_conversation), green after the implementation.

legacy_surface: conftest.py patches get_incident_transcript_reader on packages.incident_summary.service with SlackIncidentTranscriptReader over the fake client; test_slack_command_registration_surface.py changes 3 lines, the import and the two setattr targets (handler module -> service module), no assert line; INVENTORY.md:116 now cites platforms/slack.py:60 (the registration call; the old :62 was already stale).

Gates, from app/:
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 65 errors in 22 files (checked 375 source files); 0 in incident_summary, packages/incident/core or legacy_surface files. Same 65 as before the layer.
- uv run lint-imports -> Contracts: 9 kept, 0 broken. (f) reports 4 ignored imports (3 + the one temporary entry). (e) is back to 34 matched imports, the package's own adapter being gone.
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3669 passed. The same 6 known single-process order leaks as on main and layer 1 (TASK-90: test_webhooks_aws_sns.py x3, directory/test_google.py x3), which pass in isolation and under make test.
- uv run pytest tests/integration/legacy_surface -> 17 passed before the layer (on layer 1) and 17 passed after, no assertion changed.

Slice checks:
- rg -n 'Port\b|_port\b|_PORT\b|\bport\b' app/packages/incident_summary app/tests/unit/packages/incident_summary -> no match (exit 1).
- rg -n 'incident_summary' app/tests/integration/legacy_surface/conftest.py -> :31 import packages.incident_summary, :42 the service import, :53 the hookimpl tuple, :187 the get_incident_transcript_reader patch. No get_incident_channel_port for this package.
- rg -n 'get_incident_channel_port' app -> incident_draft only (its providers.py, platforms/slack.py, its unit test and conftest.py:186), which TASK-135.3 removes.
- Before deleting: rg 'incident_summary' outside the package found only tests, the legacy_surface harness and pyproject.

AC evidence: #1 handle_summarize_command makes one asyncio.run(summarize_incident_conversation(...)) call; TestHandleSummarizeCommand and the new service tests. #2 the deleted files and service.py's import from packages.incident.core.api; lint-imports. #3 the two rg outputs above. #4 legacy_surface runs; test_transcript_is_read_once_for_the_conversation_with_filtering_off and test_model_receives_author_and_text_lines_without_times. #5 the gates above.

Behaviour notes: the window start and the limit resolve as before (explicit --since from now; else the conversation's start; else now minus DEFAULT_SINCE_HOURS; limit None, unreadable or not positive -> default, capped at the maximum). Transcript-gathering log events are now the core adapter's incident_transcript_* events, as the plan's blast radius says.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 17:11
---
Re-verified TODAY against main at 8bcbf373 (2026-10-02). Since c8de7643 main gained only #1528 (blazer formatter, aws_sns_notification) and #1529 (planning records); git diff c8de7643..8bcbf373 is empty for packages/incident, packages/incident_draft, packages/incident_summary, their unit tests, tests/integration/legacy_surface, app/pyproject.toml and server/. TASK-25.10, TASK-134 and TASK-110 are still To Do and unmerged: the services still import integrations.openai and pyproject declares no entry points. No difference in code. One citation note: the class line of TranscriptMessage is service.py:40 (the plan's :39 is its decorator). platforms/slack.py is 349 lines with the helpers at :165, :204, :226, :239, :251 and the service call at :142, as planned. Delivery changed: this slice is layer 2 of the TASK-135 stack and sits on TASK-135.1's branch.
---
<!-- COMMENTS:END -->
