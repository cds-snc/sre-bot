---
id: TASK-25.1.6.2
title: Relocate the pure-domain helpers out of app/integrations/google_workspace
status: Done
assignee:
  - '@me'
created_date: '2026-09-02 14:59'
updated_date: '2026-09-03 16:51'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/layers.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/google_docs.py
  - app/integrations/google_workspace/google_drive.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 133000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md: clients "contain no business logic". Several functions in app/integrations/google_workspace/ make no outbound call at all and never did - they are pure domain logic that has been sitting in a vendor package. They need a home outside integrations/ regardless of which adapter eventually owns the SDK calls, so this slice is INDEPENDENT of every other TASK-25.1.6 child and can run first.

CONFIRMED INVENTORY (grep, 2026-09-02):
- google_calendar.py: find_first_available_slot, identify_unavailable_users, get_federal_holidays, get_utc_hour. Only get_federal_holidays touches the network (the Canada Holidays API, not a Google API) - the other three are pure computation over an already-fetched freebusy response. TASK-25.1.1's plan explicitly left them alone ("pure helpers with zero google_service dependency - untouched").
- google_docs.py: extract_google_doc_id - a regex over a URL string.
- google_drive.py: the file_type -> mimeType map and its ValueError, and the Drive q-DSL query construction in find_files_by_name / list_folders_in_folder / list_files_in_folder. TASK-25.1.5 deliberately kept these as "what google_drive.py genuinely adds over the SDK". They are still business logic in a vendor package; they move with their consuming adapter rather than in this slice, and are named here only so the inventory is complete. DO NOT move them here.
- google_directory.py: list_groups_with_members, get_members_details, convert_google_groups_members_to_dataframe. Named in TASK-25.1.6's 2026-09-01 comment. Owned by the Directory migration children (TASK-25.1.6.3/.4/.5), NOT this slice.

SCOPE OF THIS SLICE: the four Calendar helpers and extract_google_doc_id only. Move them to a non-integrations home (modules/incident already consumes all of them; a shared utility module or the incident feature's own code, chosen at planning time), update the call sites, and delete them from the vendor modules. Behaviour-neutral: these are pure functions with existing test coverage that moves with them.

WHY IT MATTERS BEYOND TIDINESS: get_federal_holidays makes an HTTP call to a NON-Google API from inside app/integrations/google_workspace/. That is a second outbound vendor hidden inside another vendor's package, invisible to the client-usage matrix and to decisions/outbound-clients.md's per-vendor checks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 google_calendar.py contains only its two Google API functions (get_freebusy, insert_event); find_first_available_slot, identify_unavailable_users, get_federal_holidays and get_utc_hour move to the new app/packages/incident/scheduling/ subpackage (decisions/migration.md rule 5 + decisions/feature-packages.md umbrella rule), with their existing tests relocated alongside them, split by decisions/testing.md tier
- [x] #2 extract_google_doc_id is explicitly OUT of this task's scope, deferred to TASK-25.1.6.7 (which owns the incident Google-boundary package decision); app/integrations/google_workspace/google_docs.py is unchanged
- [x] #3 get_federal_holidays' non-Google outbound HTTP call is no longer made from inside app/integrations/google_workspace/; its new location (app/packages/incident/scheduling/availability.py) is recorded in the task notes, along with the still-open decisions/outbound-clients.md compliance gap (no dedicated vendor client), flagged as separate tracked debt on the coordinator task
- [x] #4 app/modules/incident/schedule_retro.py imports find_first_available_slot and identify_unavailable_users from packages.incident.scheduling.availability instead of google_calendar; existing tests pass unchanged in substance
- [x] #5 No behaviour change: these are pure functions moved verbatim, with import paths updated only
- [x] #6 app/packages/incident/__init__.py is empty (umbrella namespace only) and app/packages/incident/scheduling/ ships no hookimpls and no pyproject.toml entry-point line (decisions/migration.md rule 5's bright line - not yet a registered plugin/capability)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-03, re-planned after re-scoping; destination corrected 2026-09-03 after the umbrella decision). Confirmed via read + grep: no new consumers beyond those already named. Only the 4 Calendar-availability helpers are in scope; extract_google_doc_id is explicitly deferred to TASK-25.1.6.7 (see this task's comments for why).

Source functions (verbatim bodies, no logic changes) - all from app/integrations/google_workspace/google_calendar.py: find_first_available_slot (:141), get_federal_holidays (:186), get_utc_hour (:211), identify_unavailable_users (:238). get_freebusy (:19) and insert_event (:47) stay (real Google API calls).

DESTINATION: app/packages/incident/scheduling/ - a subdomain of the incident umbrella. Authorized by decisions/migration.md rule 5 (host-surface-free pure logic may leave a frozen module ahead of its full migration) and shaped by decisions/feature-packages.md's "Complex features: an umbrella directory, never a flat prefix" rule, which rejects flat <feature>_<subfeature> naming and which rule 5 now defers to for destination choice. The earlier flat name incident_scheduling is superseded; incident_draft and incident_summary are pre-existing deviations relocated later by TASK-38, not precedent to copy.

This creates the incident umbrella directory but NOT the incident feature. app/packages/incident/__init__.py is LITERALLY EMPTY (0 bytes, matching packages/access/__init__.py) - namespace only, no docstring, because AC#6 asserts it is empty. The rule-5 explanatory docstring goes in app/packages/incident/scheduling/__init__.py. Neither ships hookimpls or a pyproject.toml entry-point line, so rule 5's bright line holds and app/modules/incident/ stays the registered incident capability until TASK-38.

Layout: packages/incident/__init__.py (empty) + packages/incident/scheduling/__init__.py (docstring only) + packages/incident/scheduling/availability.py (the 4 functions). "availability.py" is a name outside decisions/feature-packages.md's layout table; justification (per that record's "one-line justification in the PR" allowance): these are pure domain computations with no orchestrator/handler yet, so service.py ("the only orchestrator") does not fit.

Consumer (grep-confirmed, only one): app/modules/incident/schedule_retro.py:8-13 imports find_first_available_slot, get_freebusy, identify_unavailable_users, insert_event from google_calendar. get_freebusy/insert_event stay imported from google_calendar; find_first_available_slot/identify_unavailable_users move to `from packages.incident.scheduling.availability import find_first_available_slot, identify_unavailable_users` (direct-name import preserved, not `availability.fn`, because app/tests/modules/incident/test_schedule_retro.py patches `modules.incident.schedule_retro.identify_unavailable_users` / `.find_first_available_slot` directly and must keep working unmodified). This modules/ -> packages/ import is sanctioned by migration.md rule 5 for this narrow case only.

extract_google_doc_id, google_docs.py, and incident_conversation.py/incident_status.py/information_update.py are UNTOUCHED by this task (deferred to TASK-25.1.6.7).

Import pruning in google_calendar.py after removal (grep-verified no other use in the surviving file content): drop `import pytz`, `import requests`, `UTC` and `timedelta` from the datetime import (keep `datetime` for insert_event's strptime), and drop `import structlog` + `logger = structlog.get_logger()` (logger's only call site was inside get_federal_holidays). Keep cast/TYPE_CHECKING, google_service_client, convert_string_to_camel_case, generate_unique_id, CALENDAR_SCOPES.

availability.py imports (verbatim from google_calendar.py): `from datetime import UTC, datetime, timedelta`, `import pytz`, `import requests`, `import structlog`, `logger = structlog.get_logger()`.

SINGLE-PR SIZE GATE: 3 production files touched (google_calendar.py edited, availability.py new, schedule_retro.py edited) plus 2 package __init__.py files - well under 10-file/400-LOC thresholds; one subsystem; purely mechanical, behavior-neutral move. Fits a single reviewable PR - no decomposition needed.

ORDERED STEPS:
1. NEW app/packages/incident/__init__.py - EMPTY FILE (0 bytes). NEW app/packages/incident/scheduling/__init__.py - docstring only, explaining this subpackage holds relocated pure Calendar-availability logic per migration.md rule 5 and ships no hookimpls.
2. NEW app/packages/incident/scheduling/availability.py - the 4 functions verbatim (docstrings intact) in source order: find_first_available_slot, get_federal_holidays, get_utc_hour, identify_unavailable_users. Imports as above.
3. app/integrations/google_workspace/google_calendar.py - delete the 4 functions; prune imports as above.
4. app/modules/incident/schedule_retro.py - split the google_calendar import; add `from packages.incident.scheduling.availability import find_first_available_slot, identify_unavailable_users`.
5. app/tests/integrations/google_workspace/test_google_calendar.py - remove the 4 relocated functions' tests (find_first_available_slot x4, get_federal_holidays x5, get_utc_hour x7, identify_unavailable_users x9) and the fixtures exclusively used by them: est_timezone, fixed_utc_now, mock_year, time_range. Also drop `mock_datetime_now` (defined at :81, grep-confirmed zero uses - pre-existing dead fixture directly adjacent to the ones being relocated). Leave `event_details`/`calendar_service_mock` alone (also dead, but not adjacent - out of scope).
6. DONE ALREADY (working tree, uncommitted): app/tests/unit/packages/incident/scheduling/test_incident_scheduling_availability.py - pure-function tests only (no I/O): find_first_available_slot (4), get_utc_hour (7), identify_unavailable_users (9), plus fixtures est_timezone/fixed_utc_now/mock_year/time_range.
7. DONE ALREADY (working tree, uncommitted): app/tests/integration/packages/incident/scheduling/test_incident_scheduling_availability.py - get_federal_holidays tests (5), using requests_mock. Placed in integration/ not unit/ per decisions/testing.md's precedent classifying transport-layer substitution (moto/respx style) as the Integration tier; requests_mock plays the identical role for `requests` that respx plays for httpx.
8. DONE ALREADY (working tree, uncommitted): app/tests/unit/packages/incident/scheduling/test_incident_scheduling_boundaries.py - asserts the helpers are gone from integrations/google_workspace/, that schedule_retro binds the relocated ones, that google_docs.extract_google_doc_id is untouched (AC#2), that packages/incident/scheduling ships no hookimpls and no entry point, and that packages/incident/__init__.py is empty (AC#6).
9. Verification: `grep -rn` for the 4 function names under app/integrations/ returns zero; `grep -rn "incident_scheduling" app/packages app/modules` returns zero (no flat-path leftovers); run mypy/ruff/pytest per the project's validation policy.

AC TRACEABILITY:
- AC#1 (calendar helpers relocated to app/packages/incident/scheduling/, tests split by tier) -> steps 2,3,5,6,7.
- AC#2 (extract_google_doc_id explicitly out of scope) -> no code steps; asserted by step 8, verified by step 9's grep showing google_docs.py untouched.
- AC#3 (holidays HTTP call relocated, location + compliance gap recorded) -> step 2; recorded in this task's notes/comments (already posted to the coordinator TASK-25.1.6).
- AC#4 (schedule_retro.py call site updated, tests pass) -> step 4; asserted by step 8.
- AC#5 (no behavior change, verbatim move) -> all steps; verified by step 9.
- AC#6 (umbrella __init__.py empty; subpackage ships no hookimpls/entry-point) -> step 1; asserted by step 8, verified by step 9.

TEST STATE AT PLAN TIME: steps 6-8 are already written and relocated onto the umbrella paths in the working tree (untracked). ruff is clean; pytest --collect-only fails with exactly "ModuleNotFoundError: No module named 'packages.incident'" - the intended TDD red state. Implementation is steps 1-5 plus verification.

ASSUMPTIONS TO VERIFY:
- The requests_mock-based get_federal_holidays tests belong in integration/ per testing.md's transport-substitution precedent - an inference from that record's stated examples (moto/respx), not an explicit rule naming requests/requests_mock; confirm with reviewer if contested.
- `packages.incident.scheduling` as an import root (not `app.packages.incident.scheduling`) matches this repo's flat import convention per decisions/plugins.md - confirmed against packages/access/sync/__init__.py, which imports `from packages.access.common.events import ...`.

BLAST RADIUS / ROLLBACK: pure code relocation, no schema/deployment/feature-flag changes, no terraform/CI touched. A single `git revert` fully restores prior state. Any missed call site fails fast at import time (ImportError), not silently at runtime - except the mock.patch string literals, which fail at patch time; step 9's grep for "incident_scheduling" is the guard against those.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-03 (implementation agent), plan steps 1-5 + verification.

PRODUCTION CHANGES (3 files edited, 3 new):
- NEW app/packages/incident/__init__.py - 0 bytes, umbrella namespace only (AC#6).
- NEW app/packages/incident/scheduling/__init__.py - docstring only, citing decisions/migration.md rule 5. NOTE: the docstring must NOT contain the literal string 'hookimpl'; test_incident_scheduling_package_ships_no_hookimpls greps .py sources for that substring, so the first wording ('ships no hookimpls') failed the assertion. Reworded to 'registers no plugin hooks and declares no entry point'.
- NEW app/packages/incident/scheduling/availability.py - find_first_available_slot, get_federal_holidays, get_utc_hour, identify_unavailable_users moved verbatim (docstrings/comments intact); imports datetime(UTC,datetime,timedelta), pytz, requests, structlog + module logger.
- app/integrations/google_workspace/google_calendar.py - 4 functions deleted (273 -> 130 lines); pruned pytz, requests, structlog, module logger, UTC and timedelta from the datetime import. get_freebusy and insert_event unchanged.
- app/modules/incident/schedule_retro.py - google_calendar import narrowed to get_freebusy/insert_event; added 'from packages.incident.scheduling.availability import find_first_available_slot, identify_unavailable_users' as direct-name imports so the existing mock.patch targets in tests/modules/incident/test_schedule_retro.py keep working unmodified.
- app/tests/integrations/google_workspace/test_google_calendar.py - removed the 25 relocated tests and fixtures est_timezone/fixed_utc_now/mock_year/time_range plus the dead mock_datetime_now; ruff --fix then dropped the now-unused pytz and timedelta imports.
- app/integrations/google_workspace/google_docs.py UNTOUCHED (AC#2).

TEST EVIDENCE: uv run pytest tests/unit/packages/incident tests/integration/packages/incident tests/integrations/google_workspace/test_google_calendar.py tests/modules/incident/test_schedule_retro.py -> 69 passed. ruff check . clean. mypy: 94 pre-existing errors repo-wide, zero in packages/incident, google_calendar.py or schedule_retro.py.

AC#3 COMPLIANCE GAP (still open): get_federal_holidays now lives at app/packages/incident/scheduling/availability.py and no longer issues its HTTP call from inside app/integrations/google_workspace/. It still calls https://canada-holidays.ca/api/v1/holidays directly via requests with no dedicated vendor client, which remains a decisions/outbound-clients.md gap - tracked as separate debt on coordinator TASK-25.1.6, not closed here.

LEFT FOR HUMAN VERIFICATION (DoD): full 'make test' run, PR review, and moving this task to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 15:11
---
RE-SCOPED 2026-09-03 (live planning session, human-directed). Original plan (destination: app/modules/incident/utils.py) was rejected: increases debt in a frozen legacy module. First replacement idea (a minimal app/packages/incident/ foothold) was also rejected on closer reading of decisions/migration.md: the per-module recipe's "no zombie halves" guard reads as requiring the FULL incident migration (multi-PR series, already queued 2nd, largest user surface) before any packages/incident/ can exist alongside app/modules/incident/. Resolved by amending decisions/migration.md with a new coexistence rule 5 (via the architecture agent), explicitly permitting relocation of host-surface-free pure logic (no hookimpl, no entry-point) out of a frozen module into a real packages/<concern>/ home ahead of full migration - grounded in the already-shipped packages/incident_draft/packages/incident_summary precedent. Final destination: new app/packages/incident_scheduling/ package for the 4 Calendar-availability helpers, following that same incident_<concern> naming convention. extract_google_doc_id has no cohesion with that concern and is deferred to TASK-25.1.6.7 (which already owns deciding the incident Google-boundary package shape) rather than inventing a second new package name here. Acceptance criteria replaced in full to reflect this (bulk --acceptance-criteria); see decisions/migration.md's new rule 5 and change note for the authorizing amendment.
---

created: 2026-09-03 16:15
---
DESTINATION PATH CHANGE PROPOSED (2026-09-03, architecture review - needs human approval before this task's ACs are reworded).

decisions/feature-packages.md gained a "Complex features: an umbrella directory, never a flat prefix" rule this session, and decisions/migration.md rule 5 was amended so relocations land in their FINAL umbrella position rather than a flat placeholder. Under the amended rules this task's destination becomes:

  app/packages/incident_scheduling/availability.py  ->  app/packages/incident/scheduling/availability.py

with tests moving to app/tests/{unit,integration}/packages/incident/scheduling/.

WHY NOW: this is free today and not free later. The production package does not exist yet - a repo scan finds only app/tests/unit/packages/incident_scheduling/ and app/tests/integration/packages/incident_scheduling/ (tests-first, per this task's plan). Choosing the umbrella path costs one directory name; choosing the flat path costs a rename PR that TASK-38 would otherwise inherit alongside incident_draft and incident_summary.

NOTHING ELSE ABOUT THIS TASK CHANGES. app/packages/incident/__init__.py is created empty (namespace only) and app/packages/incident/scheduling/ still ships no hookimpls and no pyproject.toml entry-point line, so AC#6's bright line (migration.md rule 5's lighter path, not capability migration) holds exactly as written. The 4 relocated Calendar-availability helpers, the tier split between unit/ and integration/, and the outbound-clients.md debt flagged in AC#3 are all unaffected.

ACs AFFECTED IF APPROVED: #1 and #6 name app/packages/incident_scheduling/ literally; #3 names app/packages/incident_scheduling/availability.py. Not reworded here - human call.

TASK-38 has been updated to own the umbrella and the reconciliation of the already-shipped flat packages (incident_draft, incident_summary), and records this task as the third relocation if it is not redirected now.
---

created: 2026-09-03 16:28
---
REDIRECTED 2026-09-03 (human-approved). Destination changed from the flat app/packages/incident_scheduling/ to app/packages/incident/scheduling/, per decisions/feature-packages.md's umbrella rule and the amended decisions/migration.md rule 5 (relocations land in their final umbrella position, not a flat placeholder). ACs replaced in full; #1, #3, #4 and #6 carry the new paths, #6 additionally asserts the umbrella __init__.py is empty. #2 and #5 are textually unchanged.

ALREADY APPLIED to the working tree (tests were authored in a parallel session before the redirect, so they are updated now rather than left to drift):
- app/tests/unit/packages/incident_scheduling/ -> app/tests/unit/packages/incident/scheduling/
- app/tests/integration/packages/incident_scheduling/ -> app/tests/integration/packages/incident/scheduling/
- new empty app/tests/{unit,integration}/packages/incident/__init__.py (matches the existing convention: test subpackage __init__.py files are 0 bytes)

IT WAS NOT A DIRECTORY RENAME ONLY. Four content changes were required:
1. Import: `from packages.incident_scheduling import availability` -> `from packages.incident.scheduling import availability` (3 files).
2. Patch targets: 10 unittest.mock patch strings `packages.incident_scheduling.availability.*` -> `packages.incident.scheduling.availability.*` (8 decorators in the unit availability tests, 2 context managers in the integration tests). These are string literals, so they fail silently as AttributeError at patch time rather than at import - the exact class of breakage a rename-only pass would have missed.
3. test_incident_scheduling_boundaries.py: APP_ROOT = Path(__file__).resolve().parents[4] -> parents[5]. The extra directory level shifts the app-root walk-up; left alone this would have pointed APP_ROOT at app/tests/ and made every filesystem assertion in that file wrong-but-passing-looking.
4. test_incident_scheduling_boundaries.py: package_dir -> APP_ROOT/"packages"/"incident"/"scheduling"; the entry-point assertion changed from substring `"incident_scheduling" in target` to exact `target == "packages.incident" or target.startswith("packages.incident.")`, so it no longer accidentally matches packages.incident_draft while now also covering the umbrella; added test_incident_umbrella_is_namespace_only asserting app/packages/incident/__init__.py is empty.

Test file names kept (test_incident_scheduling_availability.py, test_incident_scheduling_boundaries.py) - still feature-prefixed and unambiguous under the new path.

VERIFIED: ruff clean on both directories; pytest --collect-only fails with exactly "ModuleNotFoundError: No module named 'packages.incident'" and nothing else, i.e. the intended TDD red state waiting on the production package.

IMPLEMENTATION NOTE for step 1: create app/packages/incident/__init__.py LITERALLY EMPTY (matching packages/access/__init__.py, which is 0 bytes) and put the rule-5 docstring in app/packages/incident/scheduling/__init__.py instead. AC#6 now asserts the umbrella file is empty, so a module docstring there would fail.

SEQUENCING CONFIRMED (human, 2026-09-03): TASK-38 stays after the TASK-25* vendor-integration cleanup; its exact position is decided once that cleanup is done. This task therefore creates the umbrella directory first, and TASK-38 later fills it and relocates incident_draft/incident_summary into it.
---
<!-- COMMENTS:END -->
