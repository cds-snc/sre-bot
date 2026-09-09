---
id: TASK-25.1.6.13
title: >-
  Configure google-api-python-client retry once at construction and retire the
  per-call num_retries drift
status: Done
assignee:
  - '@me'
created_date: '2026-09-09 15:25'
updated_date: '2026-09-09 17:23'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/client.py
  - app/infrastructure/directory/google.py
  - app/infrastructure/drive/google.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 141500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md requires SDK-native resilience 'configured once' at client construction, with no retry decision repeated at call sites. The Google surfaces do the opposite today, and the drift is spreading one provider at a time.

CURRENT STATE (grep + empirically verified against google-api-python-client 2.198.0 on 2026-09-09):
- infrastructure/directory/google.py and infrastructure/drive/google.py each define their OWN _NUM_RETRIES = 3 constant and repeat num_retries=_NUM_RETRIES at 12 .execute() call sites between them (directory/google.py:106,409,433,616,662,710,741; drive/google.py:65,74,110,203,212). Two copies of the same policy, applied by hand, easy to forget.
- integrations/google_workspace/{sheets,google_docs,google_calendar,meet,google_drive}.py and client.py::execute_google_api_request pass NOTHING, so those surfaces have zero backoff on 429/5xx.
- Two batch.execute() call sites (directory/google.py's batch round, client.py::execute_batch_request) also pass nothing; BatchHttpRequest retry is a separate SDK path from HttpRequest.execute(num_retries=...)/requestBuilder and is explicitly NOT addressed by this task (see NOT IN SCOPE).

ORDERING UPDATE (2026-09-09, human-directed): TASK-25.1.6.10.2 (infrastructure/spreadsheets/) was implemented and shipped BEFORE this task, reversing the originally-declared dependency. Validated: no conflict resulted. GoogleSpreadsheetProvider (app/infrastructure/spreadsheets/google.py) makes every .execute() call with NO arguments and defines no retry constant - it did NOT become a third copy of the drift. The practical consequence of the reversal is a real but temporary gap: Sheets calls made through GoogleSpreadsheetProvider currently have ZERO backoff on 429/5xx, unlike Drive/Directory's num_retries=3, because this task hasn't landed yet. This task closes that gap by construction. infrastructure/spreadsheets/ must NOT be touched by this task - it already inherits whatever client.py provides once construction-time retry lands, and a test here proves that inheritance rather than adding a fourth per-call copy there.

WHAT THE SDK ACTUALLY OFFERS (re-verified 2026-09-09 against the installed googleapiclient package, do not re-derive):
- googleapiclient.http.HttpRequest.execute(self, http=None, num_retries=0) is the built-in retry primitive; googleapiclient.http._retry_request implements randomized exponential backoff over 429/5xx. This IS the 'SDK's own primitive' that decisions/outbound-clients.md names for google-api-client - it is not hand-rolled retry, and it is not the time.sleep antipattern.
- discovery.build(..., num_retries=N) does NOT configure API-call retry. It is threaded only into the discovery-document fetch - do not use it for this.
- discovery.build(..., requestBuilder=HttpRequest) IS the real construction-time seam: inspected directly in the installed package - Resource.__init__ stores requestBuilder as self._requestBuilder, propagates it unchanged when constructing nested sub-resources (methodDesc dispatch), and Resource.method()'s generated request-building call does 'return self._requestBuilder(self._http, model.response, url, ...)'. A requestBuilder default of HttpRequest is what ships today; swapping in a subclass whose execute() defaults num_retries reaches every Resource built by every factory in client.py, including nested sub-resources, with zero per-call changes.

TARGET: a small HttpRequest subclass in integrations/google_workspace/client.py whose execute() defaults num_retries to a single configured value when the caller does not pass one, passed as requestBuilder from _build_service. Every Google Resource built by every factory then retries by default, once, in the vendor package where outbound-clients.md says resilience belongs. Providers and adapters call .execute() plain and make no retry decision.

THEN REMOVE THE DRIFT: delete _NUM_RETRIES and all 12 per-call num_retries arguments from infrastructure/directory/google.py and infrastructure/drive/google.py. Behavior is preserved (same retry count, now applied uniformly), and the surfaces that had no retry at all (Sheets, Docs, Calendar, Meet, the old google_drive.py) gain it for free.

SETTINGS (decided 2026-09-09, human-directed): the retry count is a typed field added to the EXISTING GoogleWorkspaceSettings at infrastructure/configuration/integrations/google.py - it is NOT moved to a new app/integrations/google_workspace/settings.py in this task. That target home doesn't exist yet; TASK-24 owns the full per-vendor settings-home migration, and the legacy home is read by 20 files / 48 references today (including GoogleResourcesConfig, which lives in the same file). decisions/configuration.md's default rule is that a task extending a domain's service migrates that domain's settings slice in the same change, but it also names an explicit interim-home escape hatch for exactly this case: creating the target home is out of scope for a change whose entire point is retry configuration. This task therefore records an interim-home comment naming app/integrations/google_workspace/settings.py as the future home and TASK-24 as its owner, rather than bundling an unrelated 20-file migration into a retry-configuration change. Default stays 3 to match what directory/drive apply today.

NOT IN SCOPE: timeouts (a separate SDK knob, no consumer has asked), asyncio.to_thread offloading of blocking SDK calls (outbound-clients.md asks for it but it is a much larger change across every provider - register it as its own task if this work makes it tempting), AWS/boto3 retry configuration, deleting execute_google_api_request (TASK-25.1.6.11), BatchHttpRequest retry behavior at the two batch.execute() call sites (a separate SDK path, unchanged, zero retry as today), any change to infrastructure/spreadsheets/ (it already complies and inherits the fix automatically), and migrating GoogleWorkspaceSettings/GoogleResourcesConfig to their target home (TASK-24; interim-home comment recorded instead).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/client.py configures SDK-native retry once at construction via a requestBuilder passed to discovery.build; no factory passes build(num_retries=...), which is verified to affect only discovery-document fetching
- [x] #2 The retry count is a typed setting (default 3) rather than a duplicated module constant
- [x] #3 infrastructure/directory/google.py and infrastructure/drive/google.py define no _NUM_RETRIES and pass no num_retries at any .execute() call site; their retry behavior is unchanged, proven by tests asserting a retried 429/5xx still succeeds through the provider
- [x] #4 A unit test proves the configured retry count reaches HttpRequest.execute by default for a Resource built through client.py, without any caller passing it
- [x] #5 No new provider or adapter is required to name a retry policy; the pattern is documented in client.py so the next Google surface inherits it
- [x] #6 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
- [x] #7 The new retry-count field is added to the existing GoogleWorkspaceSettings (infrastructure/configuration/integrations/google.py), not a new settings home; the task description/comments carry an explicit interim-home comment naming app/integrations/google_workspace/settings.py as the future home and TASK-24 as its owner
- [x] #8 app/infrastructure/spreadsheets/google.py is not modified by this task; a test proves GoogleSpreadsheetProvider's Resource (built via get_sheets_service/client.py) inherits the configured retry with zero per-call changes in that package
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read/grep/empirically verified against main, 2026-09-09)
Call sites this task removes: infrastructure/directory/google.py lines 106,409,433,616,662,710,741 (_NUM_RETRIES=3 at line 31); infrastructure/drive/google.py lines 65,74,110,203,212 (_NUM_RETRIES=3 at line 16). 12 call sites total, matching the description.
Surfaces that currently get zero retry and will gain it for free once client.py's requestBuilder lands: integrations/google_workspace/{sheets,google_docs,google_calendar,meet,google_drive}.py (all route through client.py::_build_service via get_sheets_service/get_docs_service/get_calendar_service/get_meet_service/get_drive_service) and app/infrastructure/spreadsheets/google.py (via get_sheets_service). Verified app/infrastructure/spreadsheets/google.py's four .execute() calls (lines 83,116,138,148 in that file) pass no arguments and the package defines no retry constant - confirmed compliant with the target end state already; this task adds no code there.
requestBuilder mechanism re-verified directly against the installed googleapiclient package (not re-derived from a prior task's claim): discovery.build(requestBuilder=HttpRequest) is the default; Resource.__init__ stores it as self._requestBuilder; nested sub-resources (methodDesc-based dynamic attributes) receive the same requestBuilder unchanged; the generated per-method request-building code calls "self._requestBuilder(self._http, model.response, url, ...)" to construct the HttpRequest returned before .execute(). A requestBuilder swap at each factory in client.py therefore reaches every resource and every nested sub-resource with no per-call change.
GoogleWorkspaceSettings today (infrastructure/configuration/integrations/google.py) holds GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE - flat aliases, no env_nested_delimiter. The new field follows the same flat-alias convention.
Existing test conventions: app/tests/unit/integrations/google_workspace/test_client.py monkeypatches google_client_module.build via a fake_build capturing kwargs (see _install_fake_build) and uses a local _http_error()/FakeResp helper for HttpError construction - reuse both rather than introducing new helpers. Neither app/tests/unit/infrastructure/drive/test_google_drive_provider.py nor app/tests/unit/infrastructure/directory/test_google.py currently asserts on num_retries/_NUM_RETRIES at all - retry behavior for those providers is entirely untested today, so AC#3's tests are net-new coverage, not a rewrite of existing assertions.

STEP 1 - integrations/google_workspace/client.py: construction-time retry default
Add a small HttpRequest subclass (e.g. _DefaultingRetryHttpRequest) whose execute(self, http=None, num_retries=None, **kwargs) substitutes the configured default when num_retries is None (the SDK's own default is 0, which is falsy-but-valid, so the sentinel must be None, not 0, to avoid overriding an explicit num_retries=0 caller) and delegates to super().execute(http=http, num_retries=resolved, **kwargs). Add a small factory (e.g. _build_request_builder(num_retries: int) -> Callable[..., HttpRequest]) that returns a callable matching HttpRequest's constructor signature, producing instances of the subclass with the configured default bound (via an instance attribute set post-construction, not a mutable class attribute - two services with different configured counts must never share state). _build_service passes requestBuilder=_build_request_builder(settings.GOOGLE_API_NUM_RETRIES) to build(...). A short module-level comment records the pattern so the next Google surface (there is no "next factory" step to remember - it inherits automatically) is documented for future readers, per AC#5.
Do NOT pass num_retries to discovery.build(...) itself (re-confirmed: it only threads into the discovery-document fetch, never into API-call retry).

STEP 2 - settings: infrastructure/configuration/integrations/google.py::GoogleWorkspaceSettings
Add GOOGLE_API_NUM_RETRIES: int = Field(default=3, alias="GOOGLE_API_NUM_RETRIES", description="Number of automatic retries googleapiclient applies to transient (429/5xx) API call failures, configured once at service construction."). Update the class docstring's Environment Variables list to match existing convention. No new settings file, no change to GoogleResourcesConfig. Record the interim-home note (target: app/integrations/google_workspace/settings.py; owner: TASK-24) as a code comment directly above the new field, not only in the backlog task, so a future reader of the settings file sees it too.

STEP 3 - remove the drift: infrastructure/directory/google.py and infrastructure/drive/google.py
Delete both _NUM_RETRIES = 3 constants and every num_retries=_NUM_RETRIES argument at the 12 call sites enumerated above, leaving each .execute() call plain. No other logic in either file changes - this is a subtraction-only edit at each call site.

STEP 4 - tests
integrations/google_workspace/test_client.py (extend, do not fork a new file):
  - Assert _build_service's build(...) call now includes requestBuilder=<callable> (extending the existing fake_build capture already used by test_get_admin_directory_service_builds_with_static_discovery_and_no_cache and the parametrized factory test).
  - A focused unit test on the requestBuilder factory itself: construct an HttpRequest-like double (or exercise the real HttpRequest class with a stub http/postproc/uri) through the returned builder, call .execute() with no num_retries argument, and assert the underlying execute path receives the configured default (monkeypatch googleapiclient.http.HttpRequest.execute at the parent-class level to capture the num_retries it's called with, per AC#4). A second case passes num_retries explicitly and asserts the caller's value is honored unchanged, proving the sentinel is None-based and never overrides an explicit caller value.
  - A settings test: GOOGLE_API_NUM_RETRIES defaults to 3; monkeypatch.setenv overrides it (per decisions/testing.md - never a pyproject env block).
infrastructure/directory and infrastructure/drive test suites (test_google.py, test_google_drive_provider.py): add one test each proving a simulated 429/5xx that succeeds on a later attempt still returns a success OperationResult through the provider, now that retry is construction-time rather than per-call - this is the AC#3 evidence and is net-new (no prior test covered this).
infrastructure/spreadsheets test suite (test_google_spreadsheet_provider.py, extend the existing file, do not add a new one): add one test proving a Resource obtained via the same get_sheets_service/client.py factory path carries the configured retry default with zero code change in infrastructure/spreadsheets/google.py - this is AC#8's evidence and the guard against a future contributor "fixing" that package by re-adding a per-call constant.

STEP 5 - guardrails
cd app && uv run pytest tests/unit/integrations/google_workspace tests/unit/infrastructure/directory tests/unit/infrastructure/drive tests/unit/infrastructure/spreadsheets -q; uv run mypy integrations/google_workspace/client.py infrastructure/directory/google.py infrastructure/drive/google.py infrastructure/configuration/integrations/google.py; uv run ruff check .; uv run python bin/check_sdk_typing.py. Confirm grep finds no _NUM_RETRIES and no num_retries= under infrastructure/directory/ or infrastructure/drive/, and that infrastructure/spreadsheets/ is untouched (git diff shows no changes there).

AC TRACEABILITY
AC#1 (requestBuilder configured once, num_retries not passed to build()) -> Step 1; proven by the extended fake_build capture test.
AC#2 (typed setting, default 3, not a duplicated constant) -> Step 2; proven by the new settings test.
AC#3 (directory/drive define no _NUM_RETRIES, no per-call num_retries, retry behavior unchanged) -> Step 3; proven by the new retried-429/5xx-still-succeeds tests (net-new, since no prior test covered this).
AC#4 (a unit test proves the configured count reaches HttpRequest.execute by default, no caller passing it) -> Step 4's requestBuilder factory test.
AC#5 (documented in client.py so the next Google surface inherits it) -> Step 1's module comment.
AC#6 (full suite, ruff, mypy, check_sdk_typing.py pass) -> Step 5.
AC#7 (interim-home comment; no settings-home migration in this task) -> Step 2's code comment plus this plan/description; proven by review (no new app/integrations/google_workspace/settings.py file, no consumer of GoogleWorkspaceSettings outside this file touched).
AC#8 (spreadsheets inherits automatically, zero code change there) -> Step 4's spreadsheets test; proven by a git diff showing no changes under infrastructure/spreadsheets/.

TEST MATRIX
Happy path: requestBuilder-produced request executes with the configured default when the caller passes nothing; an explicit caller-supplied num_retries is still honored.
Boundary: num_retries=0 explicitly passed by a caller must not be treated as "unset" (sentinel must be None, not falsy-check on 0).
Regression: a simulated transient 429/5xx that succeeds on retry still returns success through GoogleDirectoryProvider and GoogleDriveProvider after the per-call argument is removed.
Cross-package proof: GoogleSpreadsheetProvider (already shipped, untouched by this task) inherits the same default through the same client.py factory path.
Not covered (intentional): BatchHttpRequest retry (separate SDK path, out of scope), timeouts, asyncio.to_thread offloading, AWS/boto3 retry, execute_google_api_request deletion (TASK-25.1.6.11), and any settings-home migration (TASK-24).

ASSUMPTIONS AND DOUBTS FOR HUMAN REVIEW
(a) The sentinel for "caller didn't specify num_retries" must be None rather than 0, since the SDK's own default (0) is a valid explicit value some future caller could legitimately pass. Pinned by the explicit-value-honored test in Step 4.
(b) Nested sub-resources (e.g. spreadsheets().values()) are asserted (by direct package inspection) to receive the same requestBuilder as their parent Resource; Step 4's factory-level test targets the builder function directly rather than re-deriving this per surface, since the propagation is a discovery.py invariant, not something each vendor surface can vary.
(c) The interim-home comment is a documentation/code-comment convention, not a backlog-CLI-enforced field; if the project later wants a machine-checkable interim-home registry, that is a process improvement for TASK-24, not this task.

BLAST RADIUS AND ROLLBACK
Modifies exactly 3 production files (client.py, directory/google.py, drive/google.py) plus 1 settings file (already counted as client.py's neighbor, infrastructure/configuration/integrations/google.py) and extends existing test files (no new test files except possibly one new assertion block in the spreadsheets test file). No consumer-facing behavior changes: directory/drive keep identical retry count (3), Sheets/Docs/Calendar/Meet gain retry where they had none (a strict reliability improvement, not a behavior contract change). No terraform, no lifespan, no settings aggregator. A single git revert removes it cleanly; the only irreversible-feeling piece (new env var GOOGLE_API_NUM_RETRIES) defaults to today's effective value (3) so an unset env var is a no-op.

SIZE GATE
Production: 4 files touched (client.py, directory/google.py, drive/google.py, infrastructure/configuration/integrations/google.py), all subtraction-heavy or small-addition, one subsystem (Google Workspace vendor construction), no consumer/business-logic file touched, no mixed refactor. Comfortably inside the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented construction-time google-api-python-client retry defaults via a configured HttpRequest requestBuilder; added typed GOOGLE_API_NUM_RETRIES=3 on GoogleWorkspaceSettings with the TASK-24 interim-home note; removed directory/drive per-call retry constants and arguments; preserved plain provider execute calls and spreadsheet inheritance. Evidence: focused Google suites 188 passed; full make test reported green by the human; Ruff passed; mypy passed; bin/check_sdk_typing.py passed with no net-new SDK anti-patterns. Task remains In Progress for human review and closure.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 16:33
---
VALIDATION AFTER TASK-25.1.6.10.2 SHIPPED OUT OF ORDER (2026-09-09): confirmed no conflict. app/infrastructure/spreadsheets/google.py's four .execute() calls (lines 83,116,138,148) pass no arguments and the package defines no retry constant - it already matches this task's target end state and does not need to change when this task lands; it simply starts inheriting the configured retry through get_sheets_service -> client.py::_build_service. The description's original "third copy" framing (written when .10.2 hadn't shipped) has been revised to reflect this.

TWO SCOPE DECISIONS MADE WITH THE HUMAN, RECORDED HERE:
1. Settings home: the new GOOGLE_API_NUM_RETRIES field lands on the existing GoogleWorkspaceSettings (infrastructure/configuration/integrations/google.py) with an interim-home comment naming app/integrations/google_workspace/settings.py as the future home and TASK-24 as its owner, rather than bundling TASK-24's full 20-file/48-reference settings-home migration into a retry-configuration change. AC#7 added.
2. TASK-25.1.6.10.2's dependency metadata is left as historical record (it shipped before this task; the reversal caused no conflict) - a comment was added there instead of rewriting its dependencies field.

AC#8 added requiring a test that proves infrastructure/spreadsheets/ inherits the fix with zero code change in that package - this is the regression guard against a future contributor "fixing" that package by re-adding a per-call num_retries.
---
<!-- COMMENTS:END -->
