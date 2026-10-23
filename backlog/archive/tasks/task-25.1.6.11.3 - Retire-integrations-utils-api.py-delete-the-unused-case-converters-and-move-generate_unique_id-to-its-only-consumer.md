---
id: TASK-25.1.6.11.3
title: >-
  Retire integrations/utils/api.py: delete the unused case converters and move
  generate_unique_id to its only consumer
status: Done
assignee:
  - '@me'
created_date: '2026-09-10 17:48'
updated_date: '2026-09-10 19:49'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.7
  - TASK-25.1.6.11.1
references:
  - decisions/layers.md
  - app/integrations/utils/api.py
  - app/packages/incident/scheduling/adapters/google_calendar.py
parent_task_id: TASK-25.1.6.11
priority: medium
ordinal: 186000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of TASK-25.1.6.11. Pure deletion and move; no runtime behaviour change. Reviewed for completeness.

WHY: app/integrations/ holds vendor packages only (decisions/layers.md, decisions/outbound-clients.md). utils/ is not a vendor, and TASK-25.1.6.11.2's guardrail only warns about it. No TASK-25.* task owned this module: TASK-25.1.6.5 deliberately removed just retry_request. Human-decided 2026-09-10: none of the remaining functions justifies both its current form and its location, so the module is retired.

CONSUMERS (grep-verified on main 2026-09-10, all 7 functions):
- convert_string_to_pascal_case, convert_dict_to_pascale_case, convert_kwargs_to_pascal_case: ZERO production callers today. The only reference is a stale @patch("integrations.utils.api.convert_string_to_pascal_case") at tests/integrations/aws/test_identity_store.py:309, whose mock is unused by the code under test.
- convert_dict_to_camel_case, convert_kwargs_to_camel_case: only integrations/google_workspace/google_service.py:30/:222, deleted by TASK-25.1.7.
- convert_string_to_camel_case: integrations/google_workspace/google_calendar.py (deleted by TASK-25.1.6.11.1) and packages/incident/scheduling/adapters/google_calendar.py:25 and :90. The adapter uses it only on the body_kwargs parameter of get_freebusy and insert_event, and NO production caller passes body_kwargs: modules/incident/schedule_retro.py:48 and :338 are the only callers. That parameter is removed rather than relocated.
- generate_unique_id: the live one. packages/incident/scheduling/adapters/google_calendar.py:73 uses it for the retro event's conferenceData.createRequest.requestId. Move it verbatim into that adapter module under the same name, so the requestId format and the adapter tests' patch target stay unchanged.

THEN delete app/integrations/utils/ (api.py plus an empty __init__.py) and app/tests/integrations/utils/ (test_api.py). Carry the three generate_unique_id format tests into the adapter's test file.

NOT IN SCOPE:
- The dropped **event_config bug in insert_event: TASK-86 owns it. Do NOT start merging kwargs into the body here.
- Any redesign of the requestId: TASK-25.1.6.15 and TASK-86 decide its source and replay semantics.
- Changes to the .11.2 guardrail. Its utils warning simply goes quiet once this lands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/integrations/utils/ and app/tests/integrations/utils/ no longer exist; a repo-wide grep for integrations.utils, integrations/utils and the six case-conversion function names returns zero hits outside backlog/, tmp/ and app/tests/unit/bin/test_check_vendor_package_contract.py (whose tmp_path fixtures build a synthetic utils/api.py to exercise the guardrail's non-vendor warning)
- [x] #2 generate_unique_id is defined in packages/incident/scheduling/adapters/google_calendar.py (its __module__ is the adapter module) with an unchanged output format (three hyphen-joined 3-character [a-z0-9] segments), covered by format and uniqueness tests in the adapter's test file, and the retro event's conferenceData.createRequest.requestId is still generated per call
- [x] #3 get_freebusy and insert_event have no body_kwargs parameter (asserted via inspect.signature); modules/incident/schedule_retro.py is not modified; the adapter tests' exact events.insert and freebusy.query body assertions pass with only the body_kwargs-derived keys removed, and get_freebusy still forwards delegated_user_email
- [x] #4 The stale convert_string_to_pascal_case patch and its unused mock parameter are removed from tests/integrations/aws/test_identity_store.py with no other change to that legacy file
- [x] #5 From app/: ruff check . passes; pytest passes for tests/unit/packages/incident/scheduling, tests/unit/bin, tests/integrations/aws/test_identity_store.py and the tests/modules/incident files that reference schedule_retro; bin/check_sdk_typing.py and bin/check_vendor_package_contract.py exit 0; mypy reports no new errors (pre-existing errors in out-of-scope files and at the adapter's untouched response-parsing lines are accepted); the full pytest tests --ignore=tests/smoke run is confirmed by a human
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read-verified on main 2026-09-10; line numbers are pre-edit)
- app/integrations/utils/: api.py (89 LOC, 7 functions) and an empty __init__.py. app/tests/integrations/utils/ holds only test_api.py (no __init__.py).
- TASK-25.1.7 and TASK-25.1.6.11.1 are Done: google_service.py and integrations/google_workspace/google_calendar.py are gone. The only production importer left is packages/incident/scheduling/adapters/google_calendar.py:8.
- Adapter call sites: get_freebusy body_kwargs parameter (:17) and merge (:24-25); insert_event body_kwargs parameter (:51), time_zone extraction (:55-62), generate_unique_id (:73), merge (:89-90).
- Production callers: modules/incident/schedule_retro.py:48 get_freebusy(time_min, time_max, items) and :338 insert_event(4 positional, calendar_id=, incident_document=, **event_config). event_config holds only description, conferenceData and reminders, so neither call passes body_kwargs and dropping the 7th parameter shifts no positional argument.
- Adapter tests (tests/unit/packages/incident/scheduling/test_incident_scheduling_calendar_adapter.py): generate_unique_id patch at :92; convert_string_to_camel_case patches at :93, :169, :182 (the last two also assert `not mock_convert.called`); body_kwargs passed at :65 inside the get_freebusy delegated-user test (:57-79, the only delegated_user_email coverage for get_freebusy) and at :114 (insert_event, with "location"/"time_zone" in the expected body).
- tests/modules/incident/test_schedule_retro.py mocks get_freebusy/insert_event at the schedule_retro boundary with assert_called_once() only, so it does not evidence request bodies; the adapter tests' exact-body assertions do.
- tests/integrations/utils/test_api.py:214-245 holds four generate_unique_id tests; two overlap (character set) and their docstrings contradict the code.
- tests/unit/bin/test_check_vendor_package_contract.py:102-104,122,243 name integrations/utils/api.py inside tmp_path fake trees and a baseline assertion. They never import the real module and keep passing; they are the only expected AC#1 grep hits, hence the exclusion. bin/check_vendor_package_contract.py:46 NON_VENDOR_DIRS = {"utils"} stays (guardrail changes are out of scope); it becomes a dormant exemption.
- tests/integrations/aws/test_identity_store.py:309 patches convert_string_to_pascal_case; the mock parameter at :311 is never used in the test body.

STEP 1 - tests first (red against the current adapter)
a) Adapter test file:
  - Remove the three convert_string_to_camel_case patches, their mock parameters and the two `not mock_convert.called` assertions. Keep the generate_unique_id patch: the target name is unchanged after the move.
  - insert_event happy path: stop passing body_kwargs and drop "location"/"time_zone" from the expected body. Keep the incident_document, delegated_user_email and requestId assertions.
  - get_freebusy delegated-user test: stop passing body_kwargs, expect the three required body keys only, keep the delegated_user_email assertion.
  - Add a parametrized signature test: "body_kwargs" is not a parameter of get_freebusy or insert_event (inspect.signature).
  - Add an ownership test: generate_unique_id.__module__ is the adapter module (red until the move).
  - Replace the four legacy id tests with two behaviour tests: 100 sampled ids each fullmatch [a-z0-9]{3}-[a-z0-9]{3}-[a-z0-9]{3}, and 100 generated ids are distinct.
b) tests/integrations/aws/test_identity_store.py: remove the :309 decorator and the unused mock parameter. Legacy file: minimal edit only.
c) Delete app/tests/integrations/utils/.

STEP 2 - packages/incident/scheduling/adapters/google_calendar.py
- Replace the integrations.utils.api import (:8) with stdlib `import random` and `import string`.
- Move generate_unique_id verbatim below CALENDAR_SCOPES, keeping the public name and the `# noqa: S311` justification. Add a `-> str` return annotation.
- get_freebusy: remove the body_kwargs parameter and the :24-25 merge.
- insert_event: remove the body_kwargs parameter. Replace the :55-62 branch with `time_zone = "America/New_York"`, today's effective value for every production call, and remove the :89-90 merge. Leave **kwargs and the delegated_user_email pop untouched (see doubt a).

STEP 3 - delete app/integrations/utils/ (api.py, __init__.py)

STEP 4 - verification (from app/)
- AC#1: rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' -g '!**/test_check_vendor_package_contract.py' 'integrations[./]utils|convert_(string|dict|kwargs)_to_(camel|pascale?)_case' .. -> zero hits; both directories absent
- AC#2: rg -n 'def generate_unique_id' . -> only the adapter; ownership, format and uniqueness tests pass
- AC#3: rg -n body_kwargs . -> zero hits; signature test passes; schedule_retro.py not edited (check the PR diff)
- AC#4: the test_identity_store.py diff is the two changed lines only
- AC#5: uv run ruff check . ; uv run pytest tests/unit/packages/incident/scheduling tests/unit/bin tests/integrations/aws/test_identity_store.py tests/modules/incident/test_schedule_retro.py tests/modules/incident/test_incident_helper.py tests/modules/incident/test_incident_conversation.py tests/modules/incident/test_notify_stale_incident_channels.py ; uv run python bin/check_sdk_typing.py ; uv run python bin/check_vendor_package_contract.py ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (use a fresh --cache-dir if the shared cache raises KeyError on deserialize). The full non-smoke suite is too large for the agent loop and is run by a human.

AC TRACEABILITY
AC#1 -> Steps 1c, 2, 3; Step 4 grep.
AC#2 -> Step 2 plus the ownership, format and uniqueness tests; the happy-path test asserts the requestId comes from generate_unique_id.
AC#3 -> Steps 1a, 2; signature test, grep, unchanged exact-body assertions in the adapter tests.
AC#4 -> Step 1b.
AC#5 -> Step 4.

TEST MATRIX
- insert_event happy path: exact body with no body_kwargs-derived keys, requestId from generate_unique_id, delegated subject passes through.
- insert_event without a document omits attachments; HttpError and unclassified-error propagation keep their assertions minus the dead patch.
- get_freebusy required body, delegated-user pass-through (trimmed), error propagation and classification: unchanged behaviour.
- Signature boundary: body_kwargs absent from both adapter functions.
- generate_unique_id ownership, format and uniqueness.
- Regression: boundaries test (schedule_retro re-exports the adapter functions) and schedule_retro tests pass unmodified. Any leftover import or patch target of a removed symbol fails at collection or patch time.

ASSUMPTIONS AND DOUBTS
(a) With body_kwargs removed, a caller passing body_kwargs= would be absorbed by the remaining **kwargs and ignored, the same silent-drop shape TASK-86 reports for description/reminders. No production caller passes it. Tightening **kwargs is deliberately NOT done here: schedule_retro.py passes **event_config, so explicit parameters would turn today's silent drop into a TypeError in production. That behaviour change belongs to TASK-86.
(b) Keeping the public name generate_unique_id keeps patch targets stable. TASK-86 and TASK-25.1.6.15 may rename or replace it when they decide the requestId source.
(c) Removing a @patch whose mock is never used cannot change that test's outcome.
(d) mypy with a fresh cache reports pre-existing errors at the adapter's response parsing (:119-120, result.get("start").get("dateTime") on EventDateTime | None). Those lines are not touched: fixing them changes the exception raised for malformed responses, which is insert_event behaviour owned by TASK-86.

BLAST RADIUS AND ROLLBACK
Runtime impact: none. The removed functions have no production callers, generate_unique_id moves verbatim, and the request bodies schedule_retro produces are unchanged. A single git revert restores everything. Conflicts: TASK-86 and TASK-25.1.6.15 edit the same insert_event; whichever lands later rebases.

SIZE GATE
Production: 3 files (utils/api.py -89, utils/__init__.py deleted, adapter about -15/+14). Tests: 3 files (test_api.py deleted, adapter test about -40/+40, identity_store test -2). One subsystem, deletion and move only. Inside the gate.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
WHAT CHANGED
- app/integrations/utils/ deleted (api.py with six unused case converters, empty __init__.py).
- packages/incident/scheduling/adapters/google_calendar.py: generate_unique_id moved in verbatim (plus -> str), stdlib random/string imports replace the integrations.utils.api import; body_kwargs parameter and its camelCase merge removed from get_freebusy and insert_event; insert_event time_zone fixed to "America/New_York" (the value every production call already used). **kwargs and the delegated_user_email pop unchanged.
- tests/unit/packages/incident/scheduling/test_incident_scheduling_calendar_adapter.py: dead convert_string_to_camel_case patches and assertions removed; body_kwargs dropped from the insert_event happy path and the get_freebusy delegated-user test (delegated_user_email coverage kept); added body_kwargs signature test, generate_unique_id ownership test, and format/uniqueness tests replacing the four legacy id tests.
- tests/integrations/aws/test_identity_store.py: stale integrations.utils.api patch decorator and unused mock parameter removed (two lines).
- app/tests/integrations/utils/ deleted.
- modules/incident/schedule_retro.py and the .11.2 guardrail untouched.

EVIDENCE (from app/)
- Red before implementation: adapter test file 3 failed (2 signature cases, ownership), 10 passed.
- uv run ruff check . -> All checks passed!
- uv run pytest tests/unit/packages/incident/scheduling tests/unit/bin tests/integrations/aws/test_identity_store.py tests/modules/incident/{test_schedule_retro,test_incident_helper,test_incident_conversation,test_notify_stale_incident_channels}.py -> 255 passed
- uv run python bin/check_sdk_typing.py -> OK, exit 0; uv run python bin/check_vendor_package_contract.py -> OK, exit 0
- uv run mypy . (fresh --cache-dir; the shared .mypy_cache raises KeyError 'is_bound' on deserialize) -> Found 88 errors in 32 files, identical error set before and after the change. The adapter's two errors are the pre-existing response-parsing ones (now :122-123), accepted per AC#5.
- AC#1 grep (excluding backlog/, tmp/, test_check_vendor_package_contract.py) -> zero hits; both directories absent.
- rg 'def generate_unique_id' app -> adapter only. rg body_kwargs app -> only the signature test that asserts its absence.

OBSERVED, NOT FIXED
- An earlier full-suite run showed 6 order-dependent failures in tests/modules/webhooks/test_webhooks_aws_sns.py and tests/unit/infrastructure/directory/test_google.py; both files pass in isolation (111 passed) and are unrelated to this change.
- bin/check_vendor_package_contract.py NON_VENDOR_DIRS = {"utils"} is now a dormant exemption; removing it is a guardrail change outside this task.

REMAINING FOR HUMAN
- AC#5: run the full uv run pytest tests --ignore=tests/smoke and confirm, then check AC#5.
<!-- SECTION:NOTES:END -->
