---
id: TASK-25.1.6.11.3
title: >-
  Retire integrations/utils/api.py: delete the unused case converters and move
  generate_unique_id to its only consumer
status: To Do
assignee: []
created_date: '2026-09-10 17:48'
updated_date: '2026-09-10 17:50'
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
- [ ] #1 app/integrations/utils/ and app/tests/integrations/utils/ no longer exist; a repo-wide grep outside backlog/ and tmp/ for integrations.utils, integrations/utils and the six case-conversion function names returns zero hits
- [ ] #2 generate_unique_id is defined in packages/incident/scheduling/adapters/google_calendar.py with an unchanged output format (three hyphen-joined 3-character [a-z0-9] segments), covered by tests in the adapter's test file, and the retro event's conferenceData.createRequest.requestId is still generated per call
- [ ] #3 get_freebusy and insert_event no longer accept body_kwargs; modules/incident/schedule_retro.py is not modified and the events.insert and freebusy.query bodies it produces are unchanged
- [ ] #4 The stale convert_string_to_pascal_case patch and its unused mock parameter are removed from tests/integrations/aws/test_identity_store.py with no other change to that legacy file
- [ ] #5 ruff, mypy, pytest tests --ignore=tests/smoke and bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read-verified on main 2026-09-10; re-grep line numbers before editing)
- app/integrations/utils/: api.py (89 LOC, 7 functions) and an empty __init__.py. app/tests/integrations/utils/ holds only test_api.py (no __init__.py).
- Consumers of each function are in the description. Once TASK-25.1.7 and TASK-25.1.6.11.1 land, the only production importer is packages/incident/scheduling/adapters/google_calendar.py:8.
- Adapter call sites: get_freebusy body_kwargs parameter (:17) and merge (:24-25); insert_event body_kwargs parameter (:51), time_zone extraction (:55-62), generate_unique_id (:73), merge (:89-90).
- Production callers of the adapter: modules/incident/schedule_retro.py:48 get_freebusy(time_min, time_max, items) and :338 insert_event(4 positional, calendar_id=, incident_document=, **event_config). Neither passes body_kwargs, and dropping the 7th parameter shifts no positional argument.
- Adapter tests (tests/unit/packages/incident/scheduling/test_incident_scheduling_calendar_adapter.py): @patch of generate_unique_id at :92 and of convert_string_to_camel_case at :93, :169, :182; body_kwargs passed at :65 (get_freebusy) and :114 (insert_event, with "location"/"time_zone" in the expected body).
- tests/integrations/aws/test_identity_store.py:309 patches convert_string_to_pascal_case; the mock parameter at :311 is never used in the test body (:312-325).

STEP 1 - tests first (red against the current adapter)
a) Adapter test file:
  - Remove the three convert_string_to_camel_case patches (:93, :169, :182) and their mock parameters. Keep the generate_unique_id patch at :92: the target name is unchanged after the move.
  - insert_event happy path: stop passing body_kwargs and drop "location"/"time_zone" from the expected body. Keep the incident_document, delegated_user_email and requestId assertions.
  - Remove the get_freebusy body_kwargs test (:61-65). Add a signature test: "body_kwargs" is not a parameter of get_freebusy or insert_event (inspect.signature). This is AC#3's evidence.
  - Add the generate_unique_id format tests carried over from tests/integrations/utils/test_api.py (about :214-240): three hyphen-joined segments, each 3 characters from [a-z0-9], and 100 generated ids are distinct. Import from the adapter module. Docstrings describe behaviour only.
b) tests/integrations/aws/test_identity_store.py: remove the :309 decorator and the unused mock_convert_string_to_pascal_case parameter. Legacy file: minimal edit only.
c) Delete tests/integrations/utils/test_api.py, which leaves that directory empty.

STEP 2 - packages/incident/scheduling/adapters/google_calendar.py
- Replace the `from integrations.utils.api import ...` line (:8) with stdlib `import random` and `import string` in the import block.
- Move generate_unique_id verbatim below CALENDAR_SCOPES, keeping the public name and the `# noqa: S311` justification. Add a `-> str` return annotation.
- get_freebusy: remove the body_kwargs parameter and the :24-25 merge.
- insert_event: remove the body_kwargs parameter. Replace the :55-62 branch with `time_zone = "America/New_York"`, today's effective value for every production call, and remove the :89-90 merge. Leave **kwargs and the delegated_user_email pop untouched (see doubt a).

STEP 3 - delete app/integrations/utils/ (api.py, __init__.py)

STEP 4 - verification (from app/)
- AC#1: rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'integrations[./]utils|convert_(string|dict|kwargs)_to_(camel|pascale?)_case' .. -> zero hits; ls integrations/utils tests/integrations/utils -> both absent
- AC#2: rg -n 'def generate_unique_id' . -> only the adapter; the moved format tests pass
- AC#3: rg -n body_kwargs . -> zero hits; schedule_retro.py not edited (check the PR diff); existing schedule_retro tests pass unmodified
- AC#4: the test_identity_store.py diff is the two removed lines only
- AC#5: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke ; uv run python bin/check_sdk_typing.py

AC TRACEABILITY
AC#1 -> Steps 1c, 2, 3; Step 4 grep.
AC#2 -> Step 2 plus the moved format tests; the happy-path test asserts the requestId comes from generate_unique_id.
AC#3 -> Steps 1a, 2; signature test, grep, unchanged expected bodies in the adapter tests, and unmodified schedule_retro tests.
AC#4 -> Step 1b.
AC#5 -> Step 4.

TEST MATRIX
- insert_event happy path: body has no body_kwargs-derived keys, requestId comes from generate_unique_id, delegated subject passes through (existing, trimmed).
- insert_event without a document omits attachments; the HttpError classification/propagation tests at :169/:182 keep their assertions with only the dead patch removed.
- get_freebusy happy and error paths: existing, unchanged.
- Signature boundary: body_kwargs is absent from both adapter functions.
- generate_unique_id format and uniqueness: moved, not rewritten.
- Regression: schedule_retro tests pass unmodified, proving production call shapes are unchanged. Any leftover import or patch target of a removed symbol fails at collection or patch time.

ASSUMPTIONS AND DOUBTS
(a) With body_kwargs removed, a caller passing body_kwargs= would be absorbed by the remaining **kwargs and ignored, the same silent-drop shape TASK-86 reports for description/reminders. No production caller passes it (grep). Tightening **kwargs is deliberately NOT done here: schedule_retro.py passes **event_config, so explicit parameters would turn today's silent drop into a TypeError in production. That behaviour change belongs to TASK-86.
(b) Keeping the public name generate_unique_id keeps patch targets stable. TASK-86 and TASK-25.1.6.15 may rename or replace it when they decide the requestId source.
(c) Removing a @patch whose mock is never used cannot change that test's outcome (verified: :312-325 never reference it).
(d) AC#3's "no longer accept body_kwargs" is read as "has no body_kwargs parameter", given doubt (a).

BLAST RADIUS AND ROLLBACK
Runtime impact: none. The removed functions have no production callers once the dependencies land, generate_unique_id moves verbatim, and the request bodies schedule_retro produces are unchanged. A single git revert restores everything. Ordering: after TASK-25.1.7 (google_service.py imports the camel converters) and TASK-25.1.6.11.1 (google_calendar.py imports two functions), both enforced by dependencies. Conflicts: TASK-86 and TASK-25.1.6.15 edit the same insert_event; whichever lands later rebases.

SIZE GATE
Production: 3 files (utils/api.py -89, utils/__init__.py deleted, adapter about -15/+14). Tests: 3 files (test_api.py deleted, adapter test about -20/+30, identity_store test -2). One subsystem, deletion and move only. Inside the gate.
<!-- SECTION:PLAN:END -->
