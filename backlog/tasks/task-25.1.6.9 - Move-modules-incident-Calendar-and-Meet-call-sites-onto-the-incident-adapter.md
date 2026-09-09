---
id: TASK-25.1.6.9
title: Move modules incident Calendar and Meet call sites onto the incident adapter
status: Done
assignee: []
created_date: '2026-09-02 15:03'
updated_date: '2026-09-09 13:33'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.8.2
  - TASK-25.1.6.8.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/meet.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 140000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Smallest of the legacy-incident adapter slices; three call sites total. Follows TASK-25.1.6.7's boundary-placement decision.

CONSUMERS (grep-confirmed): modules/incident/schedule_retro.py calls google_calendar.get_freebusy and insert_event; modules/incident/core.py calls meet.create_space at two sites, both already inside the caller's own try/except.

SCOPE: the adapter builds stub-typed CalendarResource / MeetResource via get_calendar_service and get_meet_service, calls freebusy().query / events().insert / spaces().create directly, and does its own try/except + classify_google_error. modules/incident/schedule_retro.py and core.py call the adapter. integrations/google_workspace/google_calendar.py and meet.py are then deleted.

DEPENDENCY ON TASK-25.1.6.2: google_calendar.py's four pure helpers (find_first_available_slot, identify_unavailable_users, get_federal_holidays, get_utc_hour) must already have moved out of app/integrations/ before that file can be deleted. If TASK-25.1.6.2 has not landed, this slice cannot complete its deletion criterion - sequence accordingly rather than moving the helpers ad hoc here.

WATCH: core.py's existing try/except around create_space predates classification. Once the adapter classifies, decide whether that caller-side handling is still the right shape or whether it now duplicates the adapter's - and say which in the notes. Do not leave two overlapping error handlers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The incident adapter builds stub-typed CalendarResource and MeetResource via get_calendar_service/get_meet_service, calls freebusy().query, events().insert and spaces().create directly, and performs its own try/except + classify_google_error
- [x] #2 modules/incident/schedule_retro.py and modules/incident/core.py call the adapter; neither imports integrations.google_workspace
- [x] #3 app/integrations/google_workspace/google_calendar.py and meet.py are deleted with their test files, grep-verified zero references repo-wide outside backlog/ and tmp/ (requires TASK-25.1.6.2's helper relocation to have landed)
- [x] #4 core.py's pre-existing try/except around create_space is either kept with a stated reason or removed as now-duplicated adapter handling; the choice is recorded in the notes and covered by a test
- [x] #5 Existing test_schedule_retro.py, test_incident_core.py and test_meet.py coverage is preserved at the new boundary, including the delegated_user_email pass-through and HttpError propagation cases TASK-25.1.1 added
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEP 0 — Preconditions (verified, not re-done here)
- TASK-25.1.6.8.2, TASK-25.1.6.8.3 (Drive migrations) and TASK-25.1.6.2 (pure-helper relocation) are all Done.
- google_calendar.py today holds only get_freebusy/insert_event (its four pure helpers already
  relocated to packages/incident/scheduling/availability.py by TASK-25.1.6.2). meet.py holds only
  create_space. Both route through client.py::execute_google_api_request, which classifies via
  classify_google_error, logs a WARNING, then RE-RAISES (confirmed in source, not assumed).
- Repo-wide grep (excluding backlog/tmp) confirms exactly these referrers:
  google_calendar.py -> modules/incident/schedule_retro.py (import) + its own vendor test +
  tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py (2 assertions,
  see Step 4). meet.py -> modules/incident/core.py (import) + its own vendor test. No other
  consumers anywhere.
- Precision correction to the task's own text: it says "three call sites total" but there are
  four: get_freebusy x1 (schedule_event), insert_event x1 (save_retro_event), create_space x2
  (core.py: _create_meet_link_bookmark and initiate_resources_creation). Three FUNCTIONS, four
  CALL SITES. Not a scope change, just a precision note.
- Subdomain placement decision (human-confirmed via question): Calendar extends the existing
  packages/incident/scheduling/ subdomain (its only caller already imports
  packages.incident.scheduling.availability for the same retro-scheduling flow). Meet gets its
  own new packages/incident/meet/ subdomain (unrelated concern: incident Meet-link bookmarks,
  not retro scheduling) — mirrors the documents/drive precedent of one subdomain per distinct
  vendor surface/concern.

STEP 1 — packages/incident/scheduling/adapters/google_calendar.py (new)
- New packages/incident/scheduling/adapters/__init__.py (empty, matches documents/adapters and
  drive/adapters — no docstring needed there, scheduling/__init__.py already carries the rule-5
  justification for the whole subdomain).
- New packages/incident/scheduling/adapters/google_calendar.py: port get_freebusy and
  insert_event verbatim (body-building logic, CALENDAR_SCOPES constant, the
  convert_string_to_camel_case/generate_unique_id calls from integrations.utils.api — a plain
  integrations/ utility import, allowed here because this file is inside adapters/ per
  decisions/layers.md). Each function builds its CalendarResource via
  integrations.google_workspace.client.get_calendar_service(scopes=CALENDAR_SCOPES,
  delegated_user_email=...), calls freebusy().query(...).execute() / events().insert(...).execute()
  directly (no execute_google_api_request), inside its own
  try/except HttpError as exc: classify_google_error(exc); log a WARNING with status/error_code/
  retry_after; raise — i.e. re-raise after classifying+logging, NOT swallow-to-None. This
  deliberately deviates from the documents/drive adapters' log+return-sentinel shape; see Step 3
  for why.

STEP 2 — packages/incident/meet/ (new subdomain) and adapters/google_meet.py
- New packages/incident/meet/__init__.py (empty — no rule-5 docstring needed, this is a plain
  Path-B adapter subdomain like documents/drive, not a pure-logic relocation).
- New packages/incident/meet/adapters/__init__.py (empty).
- New packages/incident/meet/adapters/google_meet.py: port create_space verbatim (config dict,
  MEET_SCOPES constant), building MeetResource via get_meet_service(scopes=MEET_SCOPES,
  delegated_user_email=...), calling spaces().create(body=...).execute() directly inside the same
  try/except HttpError -> classify_google_error -> log WARNING -> raise shape as Step 1.

STEP 3 — Why the adapters raise instead of returning a sentinel (AC#1/#5 resolution)
- decisions/outbound-clients.md's adapter-is-the-boundary rule does not mandate swallowing to a
  sentinel; the documents/drive adapters chose that shape because their callers were written (or,
  for insert_event's caller, merely appear to) tolerate a degraded None/[]/{} result. Concretely
  verified here, not assumed: today's test_google_calendar.py and test_meet.py each carry explicit
  propagation tests — test_get_freebusy_propagates_http_error,
  test_insert_event_propagates_http_error, test_insert_event_propagates_unclassified_error,
  test_create_space_propagates_http_error, test_create_space_propagates_unclassified_error — all
  asserting pytest.raises(...). AC#5 requires these propagation cases to be preserved at the new
  boundary. That pins the design: the new adapters classify+log+RE-RAISE, exactly mirroring
  execute_google_api_request's current behavior, just inlined per decisions/sdk-typing.md item 3
  instead of routed through the shared Any-typed helper (which TASK-25.1.6.11 is retiring).

STEP 4 — Consumer updates (single-line import swaps, zero other production diffs)
- modules/incident/schedule_retro.py: change
  `from integrations.google_workspace.google_calendar import (get_freebusy, insert_event)` to
  `from packages.incident.scheduling.adapters.google_calendar import (get_freebusy, insert_event)`.
  Every call site (schedule_event, save_retro_event) is a bare `get_freebusy(...)`/
  `insert_event(...)` call already — no other line changes.
- modules/incident/core.py: change `from integrations.google_workspace import meet` to
  `from packages.incident.meet.adapters import google_meet as meet`. Both `meet.create_space()`
  call sites (_create_meet_link_bookmark, initiate_resources_creation) are unchanged.
- Verified: neither file imports anything else from integrations.google_workspace, so AC#2
  ("neither imports integrations.google_workspace") is satisfied by these two edits alone.

STEP 5 — AC#4: core.py's create_space try/except, resolved with a correction to the task's premise
- Site 1 (_create_meet_link_bookmark, ~line 117-132): DOES have its own
  try/except Exception around `meet.create_space()` + the subsequent `client.bookmarks_add(...)`
  call. Because the new adapter still raises (Step 3), this local except continues to catch the
  same exception it does today — the adapter's own try/except only adds classification+logging
  before re-raising, it does not change control flow. Verdict: KEEP as-is; not duplicated, it is
  the only catch at this call site and still does real work (results["errors"].append(...) +
  a domain-level log event distinct from the adapter's vendor-level warning).
- Site 2 (initiate_resources_creation, ~line 444): CORRECTION — this site has NO local
  try/except in core.py at all (verified: no try/except brackets span this line). The task's
  premise ("both already inside the caller's own try/except") is only true two frames up, at
  modules/incident/incident.py:213's generic `try: core.initiate_resources_creation(...) except
  Exception as e:` — which wraps the entire resource-creation flow (channel topic, Slack
  invites, canvas creation, etc.), not meet-specifically. Because the adapter still raises, this
  higher-level catch keeps working unchanged. Verdict: no local handling to add or remove; record
  the premise correction rather than silently treating it as true. No test changes needed here —
  behavior is unchanged by construction (the adapter's raise-on-failure is a no-op relative to
  today's execute_google_api_request raise-on-failure).
- Both verdicts are "already covered by existing tests": test_incident_core.py's
  `mock_google_meet.create_space.side_effect = Exception("meet error")` case already exercises
  site 1's except branch; site 2 has no behavior change to newly test.

STEP 6 — Delete the vendor modules and their tests
- Delete app/integrations/google_workspace/google_calendar.py and
  app/tests/integrations/google_workspace/test_google_calendar.py.
- Delete app/integrations/google_workspace/meet.py and
  app/tests/integrations/google_workspace/test_meet.py.
- Grep-verify (excluding backlog/ and tmp/) zero remaining references to google_calendar/meet
  module paths repo-wide. app/bin/baselines/sdk_typing_antipatterns.txt has no entries for either
  module today (checked) — nothing to prune there.

STEP 7 — New adapter tests (app/tests/unit/packages/incident/, per decisions/testing.md)
- New app/tests/unit/packages/incident/scheduling/test_incident_scheduling_calendar_adapter.py
  (flat under scheduling/, matching that subdomain's existing flat test convention rather than
  drive's nested adapters/ outlier): port every test_google_calendar.py test onto
  packages.incident.scheduling.adapters.google_calendar, reusing the calendar_client-style fixture
  (monkeypatch get_calendar_service on both integrations.google_workspace.client and the adapter
  module) — required args, delegated_user_email default/pass-through, optional body_kwargs,
  return-value shape, and both propagation cases for get_freebusy; the equivalent set for
  insert_event including its two propagation tests.
- New app/tests/unit/packages/incident/meet/adapters/test_incident_meet_adapter.py: port every
  test_meet.py test onto packages.incident.meet.adapters.google_meet the same way (returns_api_
  response, delegated_user_email default/pass-through, both propagation cases).
- app/tests/modules/incident/test_schedule_retro.py and test_incident_core.py need NO changes:
  both patch the consuming module's own local name (`modules.incident.schedule_retro.get_freebusy`
  / `.insert_event`, `modules.incident.core.meet`), which is unaffected by where the import
  originates — verified by how Python name binding + unittest.mock.patch work here, not assumed.

STEP 8 — Fix the now-stale scheduling boundary test
- app/tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py has two
  assertions that pin the pre-this-task state and will fail once google_calendar.py is deleted:
  - test_google_calendar_keeps_its_google_api_functions (asserts google_calendar.get_freebusy/
    insert_event are callable) — delete this test, the module no longer exists.
  - test_schedule_retro_uses_relocated_availability_helpers's last two lines (asserts
    `schedule_retro.get_freebusy is google_calendar.get_freebusy` etc.) — rewrite the identity
    checks to compare against
    packages.incident.scheduling.adapters.google_calendar.get_freebusy/insert_event instead; keep
    the availability-helper identity assertions in the same test untouched (out of this task's
    scope, still correct).
  - The RELOCATED_NAMES-parametrized tests, the umbrella-namespace-only test, and
    test_incident_scheduling_package_ships_no_hookimpls are untouched and continue to pass (the
    hookimpl check already rglobs the whole scheduling/ tree, so it automatically covers the new
    adapters/ subfolder).

STEP 9 — Validation
- Focused: pytest on the two new adapter test files, the fixed boundaries file, and
  tests/modules/incident/{test_schedule_retro.py,test_incident_core.py}.
- ruff check + check_sdk_typing.py (guardrail) on the touched/new files.
- mypy on the touched/new files specifically (whole-tree mypy has a pre-existing ~107-error
  baseline on origin/main unrelated to this work — confirm zero new errors mention the touched
  files, do not gate on the whole-tree count).
- Before handing to TASK-25.1.6.11 (which deletes execute_google_api_request repo-wide): run the
  full non-smoke suite once, per the coordinator's serialized-execution-order comment.

OPEN ITEM FOR HUMAN REVIEW (not blocking, recorded per AC#4's "recorded in the notes" requirement)
- The raise-not-swallow adapter shape (Step 3) is a deliberate, evidence-based deviation from the
  documents/drive adapters' log+return-sentinel precedent. If a future slice (e.g. TASK-25.1.6.11)
  wants a single uniform adapter error-handling contract across all incident adapters, this
  divergence should be revisited then rather than papered over now by inventing new None-handling
  in schedule_retro.py/core.py that neither file's current design calls for.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ACs verified: adapter boundary migrated to packages/incident/scheduling/adapters/google_calendar.py and packages/incident/meet/adapters/google_meet.py; schedule_retro and core now import the adapters; legacy Google Calendar/Meet module files and stale references removed; local create_space catch is intentionally retained because the adapter re-raises after classification/logging and the caller still handles domain-level bookmark creation/incident reporting. Validation: targeted pytest for the adapter, boundary, and incident consumer tests passed (60 passed).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 14:37
---
ORDERING UPDATE (2026-09-08): run after .6.8. The Calendar/Meet adapter migration is serialized behind Drive because both are legacy incident-module changes and the shared adapter boundary should be validated one slice at a time.
---

created: 2026-09-08 18:58
---
Dependency repointed 2026-09-08 (task-planner) from TASK-25.1.6.8 (now a coordinator) to its two consumer-migration children, TASK-25.1.6.8.2 and TASK-25.1.6.8.3 — both must land before this slice per the coordinator's serialized execution order. TASK-25.1.6.8.1 (the DriveProvider capability) is a transitive prerequisite of both, no direct edge needed.
---

created: 2026-09-09 13:08
---
Plan written 2026-09-09 (task-planner). Subdomain layout confirmed with human: Calendar extends packages/incident/scheduling/adapters/google_calendar.py (its only caller already uses scheduling/availability.py); Meet gets a new packages/incident/meet/adapters/google_meet.py subdomain (unrelated concern, mirrors the documents/drive one-subdomain-per-vendor-surface precedent). Key finding driving the design: today's get_freebusy/insert_event/create_space all classify+log+RE-RAISE via execute_google_api_request, and existing vendor tests (test_get_freebusy_propagates_http_error, test_insert_event_propagates_http_error/_unclassified_error, test_create_space_propagates_http_error/_unclassified_error) pin that propagation behavior, which AC#5 requires preserved at the new boundary — so these two new adapters classify+log+RAISE (not the documents/drive adapters' log+return-sentinel shape); a plan doubt records this as a deliberate deviation for human awareness. AC#4 resolved with a premise correction: core.py's SECOND create_space call site (initiate_resources_creation) has NO local try/except today (verified) — only modules/incident/incident.py's generic outer catch protects it; kept as-is since the adapter's raise-on-failure changes nothing there. Also found: tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py pins google_calendar.get_freebusy/insert_event staying in the vendor module and schedule_retro re-exporting them by identity — both assertions must be fixed/removed as part of this task (mirrors the TASK-25.1.6.7 precedent). Fits one PR (2 new small subdomains, 2 one-line consumer import swaps, 2 vendor-file deletions, 2 new adapter test files, 1 boundary-test fix); no decomposition needed.
---
<!-- COMMENTS:END -->
