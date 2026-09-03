---
id: TASK-25.1.6.2
title: Relocate the pure-domain helpers out of app/integrations/google_workspace
status: To Do
assignee: []
created_date: '2026-09-02 14:59'
updated_date: '2026-09-03 15:11'
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
- [ ] #1 google_calendar.py contains only its two Google API functions (get_freebusy, insert_event); find_first_available_slot, identify_unavailable_users, get_federal_holidays and get_utc_hour move to the new app/packages/incident_scheduling/ package (decisions/migration.md rule 5), with their existing tests relocated alongside them, split by decisions/testing.md tier
- [ ] #2 extract_google_doc_id is explicitly OUT of this task's scope, deferred to TASK-25.1.6.7 (which owns the incident Google-boundary package decision); app/integrations/google_workspace/google_docs.py is unchanged
- [ ] #3 get_federal_holidays' non-Google outbound HTTP call is no longer made from inside app/integrations/google_workspace/; its new location (app/packages/incident_scheduling/availability.py) is recorded in the task notes, along with the still-open decisions/outbound-clients.md compliance gap (no dedicated vendor client), flagged as separate tracked debt on the coordinator task
- [ ] #4 app/modules/incident/schedule_retro.py imports find_first_available_slot and identify_unavailable_users from packages.incident_scheduling.availability instead of google_calendar; existing tests pass unchanged in substance
- [ ] #5 No behaviour change: these are pure functions moved verbatim, with import paths updated only
- [ ] #6 app/packages/incident_scheduling/ ships no hookimpls and no pyproject.toml entry-point line (decisions/migration.md rule 5's bright line - not yet a registered plugin/capability)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-03, task-planner, re-planned after re-scoping). Confirmed via read + grep: no new consumers beyond those already named. Only the 4 Calendar-availability helpers are in scope; extract_google_doc_id is explicitly deferred to TASK-25.1.6.7 (see this task's comments for why).

Source functions (verbatim bodies, no logic changes) — all from app/integrations/google_workspace/google_calendar.py: find_first_available_slot (:141), get_federal_holidays (:186), get_utc_hour (:211), identify_unavailable_users (:238). get_freebusy (:19) and insert_event (:47) stay (real Google API calls).

DESTINATION: new app/packages/incident_scheduling/ package. Authorized by decisions/migration.md's new rule 5 (added this session): a frozen module's host-surface-free pure logic (no hookimpl, no entry-point) may relocate into a real packages/<concern>/ home ahead of that module's full migration. Named `incident_scheduling` following the existing `incident_draft`/`incident_summary` concern-naming convention (verified: those packages ship their own hookimpls/routes/settings and import nothing from app/modules/incident — a different but compatible precedent). This package ships NO hookimpls and NO pyproject.toml entry-point line — it is a plain importable module, not yet a registered plugin/capability (rule 5's bright line). Layout: `__init__.py` (docstring only, no hookimpls — nothing to register yet) + `availability.py` (the 4 functions). "availability.py" is a name outside decisions/feature-packages.md's layout table; justification (per that record's "one-line justification in the PR" allowance): these are pure domain computations with no orchestrator/handler yet, so `service.py` ("the only orchestrator") doesn't fit, and this is the first packages/<feature> file to hold this shape.

Consumer (grep-confirmed, only one): app/modules/incident/schedule_retro.py:8-13 imports find_first_available_slot, get_freebusy, identify_unavailable_users, insert_event from google_calendar. get_freebusy/insert_event stay imported from google_calendar; find_first_available_slot/identify_unavailable_users move to `from packages.incident_scheduling.availability import find_first_available_slot, identify_unavailable_users` (direct-name import preserved, not `availability.fn`, because app/tests/modules/incident/test_schedule_retro.py patches `modules.incident.schedule_retro.identify_unavailable_users` / `.find_first_available_slot` directly and must keep working unmodified). This is a modules/ -> packages/ import, explicitly sanctioned by migration.md rule 5 for this narrow case (not a general modules->packages allowance).

extract_google_doc_id, google_docs.py, and incident_conversation.py/incident_status.py/information_update.py are UNTOUCHED by this task (deferred to TASK-25.1.6.7).

Import pruning in google_calendar.py after removal (grep-verified no other use in the surviving file content): drop `import pytz`, `import requests`, `UTC` and `timedelta` from the datetime import (keep `datetime` for insert_event's strptime), and drop `import structlog` + `logger = structlog.get_logger()` (logger's only call site was inside get_federal_holidays). Keep cast/TYPE_CHECKING, google_service_client, convert_string_to camel_case, generate_unique_id, CALENDAR_SCOPES.

availability.py imports (verbatim from google_calendar.py — same structlog style already used elsewhere in app/packages/, e.g. packages/incident_draft/service.py, so no harmonization needed): `from datetime import UTC, datetime, timedelta`, `import pytz`, `import requests`, `import structlog`, `logger = structlog.get_logger()`.

SINGLE-PR SIZE GATE: 3 production files touched (google_calendar.py edited, 2 new files under incident_scheduling/, schedule_retro.py edited) plus package scaffolding (__init__.py) — well under 10-file/400-LOC thresholds; one subsystem; purely mechanical, behavior-neutral move. Fits a single reviewable PR — no decomposition needed. (The decisions/migration.md amendment was a separate, already-applied prerequisite, not part of this PR's diff.)

ORDERED STEPS:
1. NEW app/packages/incident_scheduling/__init__.py — docstring-only module explaining this package holds relocated pure Calendar-availability logic per migration.md rule 5, and currently ships no hookimpls. NEW app/tests/unit/packages/incident_scheduling/__init__.py and app/tests/integration/packages/incident_scheduling/__init__.py (new test directories, mirroring the new production package).
2. NEW app/packages/incident_scheduling/availability.py — the 4 functions verbatim (docstrings intact) in source order: find_first_available_slot, get_federal_holidays, get_utc_hour, identify_unavailable_users. Imports as above.
3. app/integrations/google_workspace/google_calendar.py — delete the 4 functions; prune imports as above.
4. app/modules/incident/schedule_retro.py — split the google_calendar import; add `from packages.incident_scheduling.availability import find_first_available_slot, identify_unavailable_users`.
5. app/tests/integrations/google_workspace/test_google_calendar.py — remove the 4 relocated functions' tests (find_first_available_slot x4, get_federal_holidays x5, get_utc_hour x7, identify_unavailable_users x9) and the fixtures exclusively used by them: est_timezone, fixed_utc_now, mock_year, time_range. Also drop `mock_datetime_now` (defined at :81, grep-confirmed zero test uses it — pre-existing dead fixture directly adjacent to the ones being relocated, dropped as a direct consequence of this move). Leave `event_details`/`calendar_service_mock` alone (also dead, but not adjacent to this move — out of scope).
6. NEW app/tests/unit/packages/incident_scheduling/test_incident_scheduling_availability.py — pure-function tests only (no I/O): find_first_available_slot (4), get_utc_hour (7), identify_unavailable_users (9), plus fixtures est_timezone/fixed_utc_now/mock_year/time_range.
7. NEW app/tests/integration/packages/incident_scheduling/test_incident_scheduling_availability.py — get_federal_holidays tests (5), using requests_mock. Placed in `integration/` not `unit/` per decisions/testing.md's own precedent classifying moto/respx-style transport-layer substitution as the Integration tier, not Unit; requests_mock plays the identical role for `requests` that respx plays for httpx.
8. Verification: `grep -rn` for the 4 function names under app/integrations/ returns zero; grep confirms app/packages/incident_scheduling/ has no pyproject.toml entry-point line and no `@hookimpl`; run mypy/ruff/pytest per the project's validation policy.

AC TRACEABILITY:
- AC#1 (calendar helpers relocated to app/packages/incident_scheduling/, tests split by tier) -> steps 2,3,5,6,7.
- AC#2 (extract_google_doc_id explicitly out of scope) -> no code steps; verified by step 8's grep showing google_docs.py untouched.
- AC#3 (holidays HTTP call relocated, location + compliance gap recorded) -> step 2; recorded in this task's notes/comments (already posted to the coordinator TASK-25.1.6).
- AC#4 (schedule_retro.py call site updated, tests pass) -> step 4.
- AC#5 (no behavior change, verbatim move) -> all steps; verified by step 8.
- AC#6 (package ships no hookimpls/entry-point) -> step 1; verified by step 8's grep.

ASSUMPTIONS TO VERIFY:
- decisions/migration.md's new rule 5 (added this session) is the correct authorization for this move — confirm the amendment reads as intended before implementation starts, since it was applied via a subagent in the same session as this plan.
- The requests_mock-based get_federal_holidays tests belong in `integration/` per testing.md's transport-substitution precedent — an inference from that record's stated examples (moto/respx), not an explicit rule naming `requests`/`requests_mock`; confirm with reviewer if contested.
- `packages.incident_scheduling` as an import root (not `app.packages.incident_scheduling`) matches this repo's flat import convention per decisions/plugins.md — verify against an existing package's actual working import (e.g. `from packages.geolocate...` in geolocate/__init__.py) at implementation time.

BLAST RADIUS / ROLLBACK: pure code relocation, no schema/deployment/feature-flag changes, no terraform/CI touched. A single `git revert` fully restores prior state. Any missed call site fails fast at import time (ImportError), not silently at runtime — low risk. The decisions/migration.md amendment is a separate, already-applied change (its own revert path if ever needed).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 15:11
---
RE-SCOPED 2026-09-03 (live planning session, human-directed). Original plan (destination: app/modules/incident/utils.py) was rejected: increases debt in a frozen legacy module. First replacement idea (a minimal app/packages/incident/ foothold) was also rejected on closer reading of decisions/migration.md: the per-module recipe's "no zombie halves" guard reads as requiring the FULL incident migration (multi-PR series, already queued 2nd, largest user surface) before any packages/incident/ can exist alongside app/modules/incident/. Resolved by amending decisions/migration.md with a new coexistence rule 5 (via the architecture agent), explicitly permitting relocation of host-surface-free pure logic (no hookimpl, no entry-point) out of a frozen module into a real packages/<concern>/ home ahead of full migration - grounded in the already-shipped packages/incident_draft/packages/incident_summary precedent. Final destination: new app/packages/incident_scheduling/ package for the 4 Calendar-availability helpers, following that same incident_<concern> naming convention. extract_google_doc_id has no cohesion with that concern and is deferred to TASK-25.1.6.7 (which already owns deciding the incident Google-boundary package shape) rather than inventing a second new package name here. Acceptance criteria replaced in full to reflect this (bulk --acceptance-criteria); see decisions/migration.md's new rule 5 and change note for the authorizing amendment.
---
<!-- COMMENTS:END -->
