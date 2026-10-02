---
id: TASK-135.1
title: >-
  Add packages/incident/core with the IncidentTranscriptReader interface, its
  Slack adapter and the incident umbrella import contract
status: In Progress
assignee: []
created_date: '2026-10-02 15:38'
updated_date: '2026-10-02 17:18'
labels:
  - plugin-architecture
  - features
  - slack
milestone: m-7
dependencies:
  - TASK-26.1
references:
  - decisions/feature-packages.md
  - decisions/platform-transports.md
parent_task_id: TASK-135
priority: medium
type: task
ordinal: 302000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-135 (expand). decisions/feature-packages.md umbrella rule 4: core/ holds the purpose-shaped interfaces every subdomain works on and is imported only through core/api.py.

TODAY (verified 2026-10-02 at c8de7643)
- packages/incident/ holds documents, drive, meet and scheduling; there is no core/ and no import-linter contract for the umbrella.
- incident_draft and incident_summary each define IncidentChannelPort (service.py:222 and service.py:48), returning raw Slack payloads and taking a pre-formatted Slack timestamp, and each builds the transcript in its handler (platforms/slack.py).

THIS SLICE
- Creates packages/incident/core/: one TranscriptMessage domain type, the IncidentTranscriptReader interface, its provider function get_incident_transcript_reader, and one Slack adapter. core/api.py is the only public surface.
- The interface is domain-typed: it reads a conversation's transcript since a point in time, up to a limit, as an ordered sequence of TranscriptMessage, and reports when the conversation started. Name resolution, ordering, timestamp conversion and the optional filtering of the bot's own and system messages happen behind it.
- Adds the import-linter layers contract for packages.incident.
- Nothing consumes core/ yet; no existing production module changes. TASK-135.2 and TASK-135.3 move the two packages onto it.

Human decisions 2026-10-02: the interface is IncidentTranscriptReader (role name, no Port suffix; prose says "interface"). Filtering of the bot's own and system messages is a caller choice, because draft filters today and summarize does not, and this task preserves both. documents, drive and meet do not fold into core/ here (TASK-38).

MUST NOT PREJUDGE TASK-97: core/ receives the transcript interface only. No incident record, status, channel-to-incident resolution or report interface.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 packages/incident/core/api.py exposes TranscriptMessage, IncidentTranscriptReader and get_incident_transcript_reader; the interface's signatures carry only str, int, bool, datetime and TranscriptMessage, with no Slack payload, SDK type or Slack timestamp string
- [x] #2 One Slack adapter implements the interface: chronological order, display-name resolution, timestamp conversion and the caller-selected filtering of the bot's own and system messages are covered by unit tests against a fake Web client
- [x] #3 core/ has no entrypoints/, no hookimpl and no entry point; an import-linter layers contract for packages.incident lists documents, drive, meet and scheduling as independent siblings above core, with exhaustive = true
- [x] #4 No existing production module changes other than app/pyproject.toml; the legacy_surface suite is green with no change to its files
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no import-linter ignore entry is added
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Size: 5 new production files (2 empty) plus app/pyproject.toml; about 230 production LOC added, none changed. Inside the gate. Expand step: nothing imports core/ after this PR.

DESIGN (decided)
- TranscriptMessage (core/domain.py), frozen dataclass: author: str, text: str, posted_at: datetime | None = None (timezone-aware UTC; None when the platform gave no usable time). It replaces draft's pre-formatted timestamp string and summary's two-field type in 135.2 and 135.3; formatting a time for display is the consumer's job.
- IncidentTranscriptReader (core/api.py), runtime_checkable Protocol, two methods:
  - conversation_started_at(conversation_id: str) -> datetime | None. None when the platform cannot say (lookup failed or no creation time). Callers apply their own fallback window, because DEFAULT_SINCE_HOURS is a per-command setting today.
  - read_transcript(conversation_id: str, *, since: datetime, limit: int, exclude_own_and_system_messages: bool = False) -> Sequence[TranscriptMessage]. Chronological order. Empty on a platform failure, which is today's behaviour in both handlers (they render the empty-history path).
- get_incident_transcript_reader() lives in core/api.py, lru_cache(maxsize=1), returns the Protocol type. api.py re-exports TranscriptMessage and declares __all__.
- The adapter owns every degradation and its logging (today the handlers do). Log events are named incident_transcript_* and carry conversation_id.

STEPS
1. Tests first (red), new files under app/tests/unit/packages/incident/core/ (add __init__.py to match the sibling test packages):
   - test_incident_core_transcript_read.py: SlackIncidentTranscriptReader over MagicMock(spec=WebClient).
   - test_incident_core_conversation_started_at.py: the same adapter's start lookup.
   - test_incident_core_api_surface.py: api.__all__ is exactly the three names; the provider returns an IncidentTranscriptReader, is cached, and builds on get_slack_web_client; core/ has no entrypoints directory and core/__init__.py defines no hookimpl.
2. app/packages/incident/core/__init__.py: empty.
3. app/packages/incident/core/domain.py: TranscriptMessage as above. Stdlib only.
4. app/packages/incident/core/adapters/__init__.py (empty) and adapters/slack.py: SlackIncidentTranscriptReader(client: WebClient) and build_incident_transcript_reader(). The logic is carried over from the two handlers, not redesigned:
   - conversation_started_at: conversations_info(channel=...), channel.created to an aware UTC datetime (incident_draft/platforms/slack.py:449-468, incident_summary/platforms/slack.py:251-270, minus the settings fallback).
   - read_transcript: conversations_history(channel=..., limit=limit, oldest=f"{since.timestamp():.6f}"); iterate reversed; skip a message with empty stripped text or no user; resolve the author through users_info with a per-call cache and the display_name -> profile real_name -> user real_name -> user id fallback (incident_draft :414-433, incident_summary :204-223); posted_at from float(ts), None on TypeError or ValueError (the conversion half of _format_time, :394-405).
   - With exclude_own_and_system_messages=True only: auth_test once per read, after the history call (order kept from :306-313); drop system events before resolving the author (_SYSTEM_SUBTYPES :53-67 and the channel_ prefix, :383-386); drop own messages after it, matched on user_id, bot_id or normalized name (:345-391). A failed auth_test disables the own-message filter and keeps every message.
   - With the flag False: no auth_test call and no subtype check, which is summarize's behaviour today (incident_summary :165-201).
5. app/packages/incident/core/api.py: the Protocol, the provider, the re-export.
6. app/pyproject.toml, after the access-umbrella contract (:377-386): a new contract id incident-umbrella, type layers, containers = ["packages.incident"], layers = ["documents | drive | meet | scheduling", "core"], exhaustive = true. No ignore_imports.
7. Gates from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files) ; uv run lint-imports ; uv run pytest tests --ignore=tests/smoke.

AC MAP
- #1 -> steps 3, 5; test_incident_core_api_surface.py.
- #2 -> step 4; test_incident_core_transcript_read.py, test_incident_core_conversation_started_at.py.
- #3 -> steps 2, 6; test_incident_core_api_surface.py and lint-imports output.
- #4 -> no step edits an existing production module; pytest tests/integration/legacy_surface recorded before and after.
- #5 -> step 7.

TEST MATRIX
- Happy: newest-first history comes back chronological with resolved names and posted_at; since is sent as oldest with six decimals; limit is passed through; created -> started_at.
- Boundary: empty text and user-less messages dropped; name fallbacks in order; one users_info call per distinct user; missing or malformed ts gives posted_at None; channel without created gives None; flag False keeps the bot's own posts and system events and makes no auth_test call.
- Filtering (flag True): own message matched by user_id, by bot_id alone, by normalized display name alone; another bot kept; a similarly named human kept; each _SYSTEM_SUBTYPES member and any channel_* subtype dropped.
- Failure: conversations_history raises -> empty sequence; users_info raises -> author is the user id; auth_test raises -> nothing filtered as own; conversations_info raises -> None. No exception leaves the adapter.

ASSUMPTIONS AND HOW TO VERIFY
- documents, drive, meet and scheduling do not import each other (rg '^\s*from packages|^\s*import packages' app/packages/incident found none on 2026-10-02); lint-imports confirms.
- Plugin discovery walks packages/ recursively (server/plugins/base.py:46) and will import and register packages.incident.core; with no hookimpl this is a no-op, as for packages/access/common. Confirm the app boot test still passes.
- f"{since.timestamp():.6f}" reproduces today's f"{oldest:.6f}": both sides keep microsecond precision, and a conversation's creation time is a whole second. The read test pins the string for an integer and a fractional input.
- The adapter is synchronous, like the two it replaces; the Slack concurrency model is TASK-33's.

BLAST RADIUS AND ROLLBACK
- No runtime path reaches the new code. The only way this PR breaks main is the new import-linter contract, which fails CI rather than production. A single git revert restores the previous state.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-02 as layer 1 of Stack G (handoff: doc-4), on main at 8bcbf373. Stops at In Progress for human review.

Files (new): app/packages/incident/core/__init__.py (empty), domain.py, api.py, adapters/__init__.py (empty), adapters/slack.py: 285 lines in total. app/pyproject.toml: the incident-umbrella layers contract, 11 lines added, nothing else. Tests (new): app/tests/unit/packages/incident/core/ with test_incident_core_transcript_read.py, test_incident_core_conversation_started_at.py, test_incident_core_api_surface.py and __init__.py. No existing production module and no legacy_surface file changed (git status: only pyproject.toml modified under app/).

TDD: the three test files were written first and failed at collection (ModuleNotFoundError: packages.incident.core); 48 passed after the implementation.

Gates, from app/:
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 65 errors in 22 files (checked 378 source files); 0 in packages/incident/core and tests/unit/packages/incident/core (rg count over the mypy output). The 65 are outside the touched files.
- uv run lint-imports -> Contracts: 9 kept, 0 broken, including '(i) Incident subdomains are independent siblings over core KEPT'. No ignore entry added (pyproject diff is the new contract only). Contract (e) reports 35 matched ignored imports instead of 34: its existing adapters wildcard now also matches packages.incident.core.adapters.slack -> integrations.slack.client; the ignore list itself is unchanged.
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3672 passed. The 6 are the known single-process order leaks (TASK-90), not from this change: tests/modules/webhooks/test_webhooks_aws_sns.py (3) and tests/unit/infrastructure/directory/test_google.py (3). Those two files alone: 111 passed. make test (the CI split): 2906 passed and 772 passed, 0 failed.
- uv run pytest tests/integration/legacy_surface -> 17 passed before the change and 17 passed after, with no file of the suite touched.

Slice checks:
- rg '^\s*from packages|^\s*import packages' app/packages/incident outside core/ -> no match (documents, drive, meet and scheduling do not import each other); lint-imports confirms with exhaustive = true.
- Plugin discovery imports packages.incident.core as a no-op: the app boot tests pass in the full run, and test_core_is_not_a_plugin pins no entrypoints/ or platforms/ directory and no hookimpl in core/__init__.py.

AC evidence: #1 test_incident_core_api_surface.py (__all__ is the three names; signatures carry str, int, bool, datetime and TranscriptMessage). #2 test_incident_core_transcript_read.py and test_incident_core_conversation_started_at.py over MagicMock(spec=WebClient). #3 lint-imports output above and test_core_is_not_a_plugin. #4 git status and the legacy_surface runs. #5 the gates above.

Carried over unchanged from the two handlers, as planned: the history call and its six-decimal oldest string, the name fallback and per-read cache, the system subtypes, the three own-message signals, auth_test once per filtered read after the history call. Log events are incident_transcript_* and carry conversation_id. One naming choice not in the plan: the fetched-history log field is skipped_own_and_system_messages (draft's was skipped_own_messages).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 17:11
---
Re-verified TODAY against main at 8bcbf373 (2026-10-02). Since c8de7643 main gained only #1528 (blazer formatter, aws_sns_notification) and #1529 (planning records); git diff c8de7643..8bcbf373 is empty for packages/incident, packages/incident_draft, packages/incident_summary, their unit tests, tests/integration/legacy_surface, app/pyproject.toml and server/. TASK-25.10, TASK-134 and TASK-110 are still To Do and unmerged: the services still import integrations.openai and pyproject declares no entry points. No difference: packages/incident holds documents, drive, meet and scheduling with no core/ and no umbrella contract; IncidentChannelPort is at incident_draft/service.py:222 and incident_summary/service.py:48; the access-umbrella contract is at pyproject.toml:378.
---
<!-- COMMENTS:END -->
