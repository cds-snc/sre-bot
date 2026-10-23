---
id: TASK-25.1.1
title: Migrate Google Calendar + Meet integrations off execute_google_api_call
status: Done
assignee:
  - '@me'
created_date: '2026-07-31 18:32'
updated_date: '2026-09-01 16:22'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/meet.py
parent_task_id: TASK-25.1
priority: high
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-25.1 (smallest, done first to prove the extraction pattern before the larger Drive slice). Migrate integrations/google_workspace/google_calendar.py and meet.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed Resource (CalendarResource from google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error (extend with any Calendar/Meet-specific HttpError families beyond what TASK-22.4 established for Directory). Production consumers (grep-confirmed 2026-07-31): modules/incident/schedule_retro.py (Calendar), modules/incident/core.py (Meet - only its Meet-related calls, not its Drive/other calls, which belong to sibling slices). Also delete integrations/google_workspace/gmail.py and gmail_next.py in this slice (zero production consumers, confirmed via grep; gmail_next.py is also named for deletion in TASK-23's plan - coordinate to avoid double-deleting, verify TASK-23's status at implementation time).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/google_calendar.py and meet.py no longer call execute_google_api_call; both route through a factory-built, stub-typed Resource + classify_google_error, raising/classifying per the outbound-clients.md contract
- [x] #2 modules/incident/schedule_retro.py (Calendar) and the Meet-related calls in modules/incident/core.py behave identically (existing tests pass, behavior-neutral)
- [x] #3 gmail.py is deleted (gmail_next.py was already deleted by TASK-23.1, Done 2026-08-31 -- no double-deletion risk); classify_google_error gains any Calendar/Meet-specific mapped families with unit coverage under tests/unit/integrations/google_workspace/
- [x] #4 New unit test coverage exists for meet.py's create_space under tests/integrations/google_workspace/test_meet.py (previously untested; test_google_meet.py covers only the unrelated google_meet.py URL-builder module), covering success, delegated_user_email pass-through, and HttpError propagation
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
CONTEXT VERIFIED (2026-09-01, task-planner): TASK-22.4 (dep) is Done and established the canonical vendor-client pattern this slice must mirror: integrations/google_workspace/client.py exports get_admin_directory_service(scopes, delegated_user_email=None) -> AdminDirectoryResource (TYPE_CHECKING-only stub import from googleapiclient._apis.admin.directory_v1, build(..., cache_discovery=False, static_discovery=True)) and classify_google_error(exc) -> tuple[OperationStatus, str|None, int|None] (maps HttpError.resp.status: 404->NOT_FOUND, 401/403->UNAUTHORIZED, 429/500/502/503/504->TRANSIENT_ERROR w/ retry-after, else raise; non-HttpError always raises). google-api-python-client-stubs is installed and confirmed to expose CalendarResource (googleapiclient._apis.calendar.v3) and MeetResource (googleapiclient._apis.meet.v2), both importable the same way as AdminDirectoryResource.

STALE TASK TEXT CORRECTED (AC#3 reworded 2026-09-01, human-confirmed): TASK-23.1 (Delete the Google _next dispatcher generation) is Done and already deleted gmail_next.py (and google_directory_next.py, google_service_next.py). This slice only deletes gmail.py (zero production consumers, confirmed via grep) -- no double-deletion risk.

CALL-SITE INVENTORY (fresh grep, 2026-09-01):
- google_calendar.py: only get_freebusy (app/integrations/google_workspace/google_calendar.py:15) and insert_event (google_calendar.py:47) call google_service.execute_google_api_call. find_first_available_slot, identify_unavailable_users, get_federal_holidays, get_utc_hour are pure helpers with zero google_service dependency -- untouched.
- meet.py: only create_space (app/integrations/google_workspace/meet.py:10) calls execute_google_api_call.
- gmail.py: zero production consumers (grep confirmed); its only test is app/tests/integrations/google_workspace/test_gmail.py.
- Production consumers: app/modules/incident/schedule_retro.py:8-13 imports find_first_available_slot/get_freebusy/identify_unavailable_users/insert_event from google_calendar (module-level function calls, not internals). app/modules/incident/core.py:9,117,443 calls meet.create_space() at two call sites, both already wrapped in the caller's own try/except (core.py:112-137 and the enclosing handler around line 443) -- google_drive usage in core.py is explicitly out of scope (TASK-25.1.5).
- Stub-verified method shapes (googleapiclient-stubs .venv/lib/python3.14/site-packages/googleapiclient-stubs/_apis/{calendar/v3,meet/v2}/resources.pyi): CalendarResource.freebusy().query(body: FreeBusyRequest), CalendarResource.events().insert(calendarId, body: Event, conferenceDataVersion, sendUpdates, supportsAttachments, ...) -- exact match to today's execute_google_api_call kwargs. MeetResource.spaces().create(body: Space) -- exact match to today's call.
- Test coverage gap found: no test file exists today for meet.py's create_space (app/tests/integrations/google_workspace/test_google_meet.py tests the unrelated google_meet.py URL-builder module, not meet.py). Closed by AC#4 / Step 6 below.
- test_google_calendar.py has 9 test functions patching google_calendar.google_service.execute_google_api_call; all 9 need their mock target changed to the new factory+Resource chain. One of the 9 (test_insert_event_api_call_error) asserts pytest.raises(Exception) but its caplog assertion is unreachable dead code (placed after the raising call inside the `with pytest.raises` block) -- no real log-message constraint to preserve.

RESOLVED (human, 2026-09-01): execute_google_api_request's placement in client.py is a DELIBERATE, TEMPORARY, DOCUMENTED deviation from decisions/outbound-clients.md's "exactly: factories, classify_<vendor>_error, settings" export contract -- not a silent violation, and not assumed permanent. It must not be treated as done-and-forgotten: TASK-25.1.6 (new subtask, dep on this task + TASK-25.1.2/.3/.4/.5) is created to force an explicit decision, once all Google Workspace vendor slices are Done, between (a) inlining classify_google_error+logging per call site and deleting the helper, or (b) formalizing it with an outbound-clients.md update. This task's own PR description and implementation notes must reference TASK-25.1.6 when the helper is added, so the deviation is traceable from the code, not just the backlog.

STEPS
1. app/integrations/google_workspace/client.py: add two new factory functions mirroring get_admin_directory_service's shape exactly (settings via get_google_workspace_settings(), same delegated-email-default-to-SRE_BOT_EMAIL logic, same cache_discovery=False/static_discovery=True build() call):
   - get_calendar_service(scopes: list[str], delegated_user_email: str | None = None) -> CalendarResource (build('calendar','v3',...))
   - get_meet_service(scopes: list[str], delegated_user_email: str | None = None) -> MeetResource (build('meet','v2',...))
   Add both stub imports under the existing `if TYPE_CHECKING:` block (from googleapiclient._apis.calendar.v3 import CalendarResource; from googleapiclient._apis.meet.v2 import MeetResource).
   Add one small shared helper, execute_google_api_request(request: Any) -> Any, next to the existing execute_batch_request: calls request.execute() inside try/except, calls classify_google_error(exc) (which itself raises the original exception for unmapped/non-HttpError cases), logs the classified status/error_code/retry_after for mapped cases, then re-raises the original exception unconditionally (never swallows). This is shared by google_calendar.py (2 call sites) and meet.py (1 call site) to avoid duplicating the try/except/classify/log/raise shape 3 times, and gives TASK-25.1.2/.3/.5 (sibling Docs/Sheets/Drive slices) a ready-made reusable primitive. Add a code comment on execute_google_api_request itself stating it is a temporary shared primitive pending TASK-25.1.6's inline-vs-formalize decision, and reference TASK-25.1.6 in the PR description / implementation notes.
   Do NOT add new classify_google_error status mappings speculatively -- the existing 404/401/403/429/5xx table is generic across all Google APIs; if Calendar/Meet raise an unmapped status (e.g. 400 invalid-argument), it propagates per the existing contract ("unexpected exceptions are not classified"). No evidence found requiring new families; confirm via the live/failure-path tests in step 4 whether any Calendar/Meet-specific status needs adding, and only add it then with a comment citing the observed status.

2. app/integrations/google_workspace/google_calendar.py: convert get_freebusy and insert_event off execute_google_api_call:
   - get_freebusy: pop delegated_user_email from **kwargs (default None), call service = google_service_client.get_calendar_service(scopes=["https://www.googleapis.com/auth/calendar"], delegated_user_email=delegated_user_email), build the same body dict as today, call google_service_client.execute_google_api_request(service.freebusy().query(body=body)).
   - insert_event: same delegated_user_email extraction; call service.events().insert(calendarId=calendar_id, body=body, supportsAttachments=True, sendUpdates="all", conferenceDataVersion=1).execute() via execute_google_api_request. Keep the existing result-shape handling (result.get("htmlLink")/result.get("start").get("dateTime")) unchanged -- the isinstance(result, tuple) branch becomes dead code (execute_google_api_request never returns a tuple) and should be deleted, not kept as unreachable code.
   - Remove the `handle_google_api_errors = google_service.handle_google_api_errors` re-export and the `@handle_google_api_errors` decorators from these two functions (superseded by execute_google_api_request's own classify+log+raise); keep the `from integrations.google_workspace import google_service` import only if still needed elsewhere in the file (check after edit -- likely removable entirely once both functions are migrated, since no other function in this file uses google_service).

3. app/integrations/google_workspace/meet.py: convert create_space off execute_google_api_call the same way: pop delegated_user_email from **kwargs, call service = get_meet_service(scopes=["https://www.googleapis.com/auth/meetings.space.created"], delegated_user_email=delegated_user_email), return execute_google_api_request(service.spaces().create(body={"config": config})). Remove the `handle_google_api_errors`/`execute_google_api_call` imports from google_service; this file no longer depends on google_service.py at all.

4. Delete app/integrations/google_workspace/gmail.py and app/tests/integrations/google_workspace/test_gmail.py (zero production consumers, reconfirm via grep immediately before deleting in case anything changed since planning).

5. Rework app/tests/integrations/google_workspace/test_google_calendar.py: all 9 tests patching `google_calendar.google_service.execute_google_api_call` are rebuilt to patch `google_calendar.google_service_client.get_calendar_service` (or the module-level import name chosen in step 2) returning a MagicMock service, with the mocked service's `.freebusy().query(body=...).execute()` / `.events().insert(...).execute()` chain set to return the same fixture dicts used today. Preserve every existing assertion on the resulting business-logic output (event_info/event_link strings, htmlLink parsing, etc.) unchanged -- only the mock's construction/call-shape changes, per the same mechanical pattern TASK-22.3/22.4 already established for AWS/Directory fakes. The dead isinstance(result, tuple) assertions/paths in the source no longer apply; do not preserve tests for them.

6. Add app/tests/integrations/google_workspace/test_meet.py (new file, closes the coverage gap found in research; AC#4): unit tests for create_space covering (a) success path -- mocked get_meet_service/service chain returns a spaces dict, function returns it unchanged; (b) delegated_user_email pass-through -- asserts the captured scopes/delegated_user_email argument reaching get_meet_service; (c) HttpError propagation -- mocked chain raises an HttpError, asserts the same exception type propagates (not swallowed, not wrapped).

7. Extend app/tests/unit/integrations/google_workspace/test_client.py with: get_calendar_service and get_meet_service construction tests (mirroring test_get_admin_directory_service_builds_with_static_discovery_and_no_cache: asserts build() called with the right service/version/cache_discovery/static_discovery, and delegated-email default-to-SRE_BOT_EMAIL behavior) and execute_google_api_request tests (success passthrough; HttpError classified+logged+re-raised; non-HttpError propagates unclassified via classify_google_error's own raise).

8. Prune app/bin/baselines/sdk_typing_antipatterns.txt if google_calendar.py/meet.py/gmail.py appear there (mirrors TASK-23.1's step 6 precedent); its header states removals are always safe.

9. Re-run repo-wide checks: grep for execute_google_api_call in google_calendar.py/meet.py (expect zero); grep for gmail.py repo-wide outside backlog/tmp (expect zero); bin/check_sdk_typing.py; bin/check_deprecated_infra_client_imports.py; bin/generate_client_usage_matrix.sh.

AC-TO-STEP-TO-TEST
- AC#1 (google_calendar.py/meet.py route through factory+Resource+classify_google_error) -> Steps 1-3. Verified by: grep for execute_google_api_call in both files returns zero; mypy resolves get_calendar_service/get_meet_service's stub-typed returns and the chained .freebusy()/.events()/.spaces() calls with no Any leakage; Steps 5-7 tests.
- AC#2 (schedule_retro.py + core.py's Meet calls behave identically) -> Steps 2-3 (internals only, public function signatures/return shapes unchanged) + existing app/tests/modules/incident/test_schedule_retro.py and app/tests/modules/incident/test_incident_core.py + test_recreate_missing_resources.py (all mock at the google_calendar/meet module-function boundary, confirmed unaffected by internal rewiring) run green with zero edits.
- AC#3 (gmail.py deleted; classify_google_error gains any needed families with coverage) -> Step 4 (gmail.py deletion) + Step 1's explicit decision not to speculatively extend classify_google_error, revisited only if Step 5/6 failure-path tests surface an unmapped status that needs a family, in which case add it with justification.
- AC#4 (meet.py test coverage gap) -> Step 6.

TEST MATRIX
Happy path: get_freebusy/insert_event/create_space each return the same shape as today given a mocked successful Resource chain. Delegated-email: default-to-SRE_BOT_EMAIL and explicit-override cases for all three functions (insert_event's is already tested; get_freebusy/create_space gain equivalent coverage). Error propagation: HttpError with a classified status (e.g. 429) logs and re-raises unchanged; HttpError with an unmapped status and a non-HttpError exception both propagate via classify_google_error's own raise, unchanged exception identity. Construction: get_calendar_service/get_meet_service build() call assertions (service/version/cache_discovery=False/static_discovery=True) mirroring test_get_admin_directory_service_builds_with_static_discovery_and_no_cache. Regression: full existing app/tests/modules/incident/{test_schedule_retro.py,test_incident_core.py,test_recreate_missing_resources.py} suites green with zero edits (proves AC#2 module-boundary behavior neutrality). Commands: cd app && uv run pytest tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/incident -v; then make test (project's CI split); then uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; then uv run ruff check .; then bin/check_sdk_typing.py, bin/check_deprecated_infra_client_imports.py, bin/generate_client_usage_matrix.sh.

ASSUMPTIONS AND DOUBTS (verify at impl)
(a) execute_google_api_request's long-term home (client.py vs. per-file) is intentionally deferred, not re-litigated here -- see TASK-25.1.6.
(b) Whether any Calendar/Meet HttpError status needs a new classify_google_error family beyond the existing table -- no evidence found in current code/tests; only add if a failure-path test in Step 6/7 surfaces one, with the observed status cited in the commit.
(c) insert_event's **kwargs today silently drops any stray unsupported kwarg via the old dispatcher's docstring-based filtering; the new direct-call design only extracts delegated_user_email and would raise a TypeError on any other stray kwarg reaching events().insert(). Zero production call sites pass anything beyond delegated_user_email (grep-confirmed), so this is a theoretical behavior change with no real-world trigger -- accepted, not blocking.
(d) client.py's existing classify_google_error has an `except TypeError, ValueError:` bare-tuple except clause (valid under this repo's pinned Python 3.14 grammar, confirmed by direct interpreter test) -- pre-existing from TASK-22.4, out of this slice's scope, not touched.

BLAST RADIUS / ROLLBACK
Contained to integrations/google_workspace/{client.py,google_calendar.py,meet.py} (edits), gmail.py (deletion), and their test files (2 reworked/added, 1 deleted, 1 extended). No infrastructure/, packages/, terraform/, or CI changes. schedule_retro.py and core.py are untouched (consumers of the same public function signatures). Single git revert restores the execute_google_api_call-based implementation. No ordering constraint against sibling slices TASK-25.1.2/.3/.4/.5 (each touches disjoint files); google_service.py itself stays alive for those siblings' remaining consumers. TASK-25.1.6 (new) depends on this task and runs strictly after, so it adds no risk to this PR.

SIZE GATE: fits comfortably in one PR. Production diff: 4 files (client.py ~60-90 new LOC for 2 factories + 1 shared helper; google_calendar.py ~30 LOC net changed; meet.py ~15 LOC net changed; gmail.py ~90 LOC deleted). Test diff: 1 file deleted (test_gmail.py), 1 file reworked (test_google_calendar.py, mechanical mock-target change across 9 tests), 1 new file (test_meet.py, ~60-80 LOC), 1 file extended (test_client.py, ~60-80 LOC). Single subsystem (Google Workspace vendor client), no cross-cutting refactor, no packages/ changes -- smaller than TASK-22.4's already-approved single-PR precedent.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented (2026-09-01).

CHANGES
- integrations/google_workspace/client.py: added get_calendar_service (calendar/v3) and get_meet_service (meet/v2) mirroring get_admin_directory_service; extracted shared _build_service for credential/delegation/build logic (cache_discovery=False, static_discovery=True). Added execute_google_api_request(request) shared primitive: executes, classifies failures via classify_google_error, logs classified status/error_code/retry_after, always re-raises the original exception. Marked temporary in-code pending TASK-25.1.6's inline-vs-formalize decision. Stub imports (CalendarResource, MeetResource) added under TYPE_CHECKING; factory returns cast to their stub types (also removes a pre-existing no-any-return on the Directory factory).
- google_calendar.py: get_freebusy/insert_event now build a stub-typed CalendarResource via the factory and call .freebusy().query()/.events().insert() through execute_google_api_request. Removed handle_google_api_errors decorators + the google_service import entirely. Deleted the dead isinstance(result, tuple) branch.
- meet.py: create_space migrated the same way; no longer imports google_service.
- Deleted integrations/google_workspace/gmail.py and tests/integrations/google_workspace/test_gmail.py (zero production consumers, re-grepped before deletion).
- Pruned gmail.py/google_calendar.py/meet.py from bin/baselines/sdk_typing_antipatterns.txt (16 baselined files remain).
- classify_google_error NOT extended: no Calendar/Meet status surfaced by the failure-path tests fell outside the existing 404/401/403/429/5xx table; unmapped statuses propagate per the existing contract.

TEST EVIDENCE
- tests/integrations/google_workspace + tests/unit/integrations/google_workspace + tests/modules/incident: 428 passed (includes pre-authored test_meet.py create_space coverage: success, delegated_user_email pass-through/default, HttpError propagation, non-HttpError propagation; and test_client.py factory-construction + execute_google_api_request coverage).
- modules/incident/schedule_retro.py and core.py untouched; their suites green with zero edits (AC#2 behavior neutrality).
- Full suite: 3014 passed. 3 failures in tests/modules/webhooks/test_webhooks_aws_sns.py are pre-existing cross-test pollution (file passes 12/12 in isolation) and unrelated to this change.
- mypy: 100 errors / 35 files (down from 107 / 38 pre-change); zero in client.py, google_calendar.py, meet.py. ruff: clean. bin/check_sdk_typing.py and bin/check_deprecated_infra_client_imports.py: OK. bin/generate_client_usage_matrix.sh regenerated.

FOR HUMAN VERIFICATION (DoD)
- PR description must reference TASK-25.1.6 for the execute_google_api_request placement deviation from decisions/outbound-clients.md.
- Confirm gmail.py removal is acceptable (no production consumers found).
- Live-path smoke of Calendar retro scheduling / Meet space creation against real Google APIs (not covered by unit tests).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:24
---
PLANNING NOTE (2026-09-01): AC#3's 'gmail.py and gmail_next.py are deleted' is now stale -- TASK-23.1 (Done, 2026-08-31) already deleted gmail_next.py repo-wide. This slice only needs to delete gmail.py (zero production consumers, reconfirmed). Recommend re-wording AC#3 to drop the gmail_next.py clause when convenient (not removing it via CLI myself per hand-edit-avoidance; flagging for human confirmation instead). Also flagging one design choice for confirmation before implementation: the plan places a new shared execute_google_api_request(request) helper in integrations/google_workspace/client.py (alongside execute_batch_request) to avoid duplicating a try/except+classify_google_error+log+raise shape across get_freebusy/insert_event/create_space (3 call sites, 2 files) -- recommended over per-file duplication, and intended to be reused by sibling slices TASK-25.1.2/.3/.5. Please confirm this is acceptable scope for this slice before implementation starts.
---
<!-- COMMENTS:END -->
