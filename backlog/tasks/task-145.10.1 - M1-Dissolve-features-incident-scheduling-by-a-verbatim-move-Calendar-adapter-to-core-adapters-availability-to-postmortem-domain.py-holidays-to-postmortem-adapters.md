---
id: TASK-145.10.1
title: >-
  M1 Dissolve features/incident/scheduling by a verbatim move (Calendar adapter
  to core/adapters, availability to postmortem/domain.py, holidays to
  postmortem/adapters)
status: In Progress
assignee: []
created_date: '2026-11-20T22:04:00Z'
updated_date: '2026-11-20T22:28:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.6
parent_task_id: TASK-145.10
priority: medium
ordinal: 532000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack M layer M1 of TASK-145.10. Mechanical, no behaviour change: the adapter-only sibling features/incident/scheduling/ is dissolved because contract (i) makes postmortem and scheduling independent siblings and incident-management.md:98,:179 retire adapter-only siblings. Calendar adapter -> core/adapters/google_calendar.py beside google_meet.py; availability.py pure functions -> postmortem/domain.py; get_federal_holidays verbatim -> postmortem/adapters/public_holidays.py; legacy schedule_retro.py imports repointed (migration.md rule 2); contract (i) drops scheduling; package_shape baseline entry and the seam baseline lines moved; ADR lines amended. Branch stack-m/145.10.1-dissolve-scheduling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 scheduling/ no longer exists; the Calendar adapter is core/adapters/google_calendar.py, the pure availability functions are postmortem/domain.py and the holiday function is postmortem/adapters/public_holidays.py, all moved verbatim (only imports and module docstrings change)
- [x] #2 modules/incident/schedule_retro.py imports the new paths and the pinned retro flow (test_incident_retro_schedule_surface.py) passes unchanged
- [x] #3 pyproject contract (i) no longer lists scheduling; bin/baselines/package_shape.txt entry for scheduling/availability.py is deleted; test_seams_strict.txt scheduling lines are re-keyed to the moved tests, none added
- [x] #4 incident-management.md :75 (stale TASK-138 calendar sentence), :137 and :179 are amended; features/incident/README.md scheduling and postmortem rows updated
- [x] #5 No behaviour change and no rule-3 exception; ruff, mypy, make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Full plan, grounded on main ac8f8186 (2026-11-20). Mechanical only: no logic line changes, no behaviour change, no rule-3 exception (no new seam; two strict seam lines are re-keyed, one is removed by the move, see step 6).

## Discovered state
- features/incident/scheduling/ (adapter-only sibling, no hookimpl): availability.py (152 lines: find_first_available_slot :14, get_federal_holidays :59, get_utc_hour :84, identify_unavailable_users :112), adapters/google_calendar.py (128 lines: generate_unique_id :18, get_freebusy :33, insert_event :58), two __init__.py. Only modules/incident/schedule_retro.py imports them (imports lines 8-15; calls schedule_event :22-60 and save_retro_event :309-343).
- pyproject.toml contract (i) :385-392 lists "comms | postmortem | response | scheduling | scribe" as independent siblings (exhaustive), so postmortem cannot import scheduling; incident-management.md :98 and :179 retire adapter-only siblings ("scheduling remains until its rebuild").
- Baselines: bin/baselines/package_shape.txt:15-16 (availability.py, owner TASK-145.10); bin/baselines/test_seams_strict.txt:39-41 (tests/unit/features/incident/scheduling/... patch get_federal_holidays, generate_unique_id, logger.warning).
- Tests: tests/unit/features/incident/scheduling/{test_incident_scheduling_availability.py (339), test_incident_scheduling_calendar_adapter.py (231), test_incident_scheduling_boundaries.py (64)}, tests/integration/features/incident/scheduling/test_incident_scheduling_availability.py (holidays via requests_mock), tests/modules/incident/test_schedule_retro.py (legacy, patches the old paths).
- Pins (tests/integration/legacy_surface/test_incident_retro_schedule_surface.py) fake only the Google service edge and requests.get, so they pass unchanged with the moved code.
- ADR lines: incident-management.md :75 (stale: "calendar operations are the calendar workplace capability (TASK-138)"), :137, :179; workplace-systems.md :70, :91 (scheduling stays incident-owned: consistent, wording to match); features/incident/README.md rows 21-22, :47, :167-169.

## Steps (two commits: move, then references)
1. git mv scheduling/adapters/google_calendar.py -> core/adapters/google_calendar.py (docstring: the adapter is core's, beside google_meet.py; code verbatim).
2. Split availability.py verbatim: find_first_available_slot, get_utc_hour, identify_unavailable_users -> features/incident/postmortem/domain.py (pure; find_first_available_slot stays verbatim and calls get_federal_holidays, imported from postmortem/adapters/public_holidays.py; postmortem may import its own adapters, so no contract issue; M2b replaces the call with the injected holiday set). get_federal_holidays -> postmortem/adapters/public_holidays.py verbatim (adapters/ __init__.py added; it imports requests, not integrations; M2a replaces it with the HolidayCalendar adapter over integrations/canada_holidays).
3. Delete features/incident/scheduling/ (4 files).
4. modules/incident/schedule_retro.py: repoint the four imports (core.adapters.google_calendar, postmortem.domain). Legacy importing features is allowed (contract (g) forbids the reverse). postmortem/__init__.py docstring updated; it stays a plain package (no hookimpl, not an entry point).
5. pyproject.toml contract (i): remove scheduling from the siblings line. package_shape.txt: delete lines 15-16 (and its comment).
6. Tests: git mv the unit tests to tests/unit/features/incident/postmortem/test_incident_postmortem_slot_search.py (from availability tests), tests/unit/features/incident/core/test_incident_core_calendar_adapter.py, tests/integration/features/incident/postmortem/test_incident_postmortem_public_holidays_fetch.py; delete test_incident_scheduling_boundaries.py (its subject, the package, is gone; keep nothing that asserts a path that no longer exists). Re-key the three test_seams_strict.txt lines to the moved paths and patched targets (same three seams, owner unchanged until M2a/M2b delete them); no entry added. tests/modules/incident/test_schedule_retro.py patch targets updated.
7. ADR and docs: incident-management.md :75 (calendar operations are incident-owned over integrations/google_workspace; TASK-138 superseded by TASK-169; a capability waits for a non-incident consumer), :137 and :179 (scheduling dissolved by TASK-145.10.1 into core/adapters and postmortem); workplace-systems.md :70 and :91 wording; features/incident/README.md rows and :47, :167-169.

## AC traceability
AC1 steps 1-3,5; AC2 step 4 and the unchanged pins; AC3 steps 5-6; AC4 step 7; AC5 gates below.

## Test matrix
No new behaviour: every moved test passes unchanged except import paths. Boundary: pins green; make check-import-contracts proves (i) without scheduling; make check-package-shape proves the baseline shrinks (stale-entry report); make check-test-seams proves no net-new seam.

## Assumptions to verify
- core/adapters/google_calendar.py needs no contract (i) exception (core may import integrations only from adapters/: allowed list). Verify with make check-import-contracts.
- postmortem/domain.py importing postmortem/adapters/public_holidays.py is within one subdomain (free imports). It is temporary until M2b.
- TASK-181 (Calendar and Meet factories) may change get_calendar_service's signature; whichever merges second adapts.

## Size
About 25 new LOC (headers, one __init__), about 280 LOC moved verbatim, 4 files deleted, about 12 files touched (docs counted). Under the gate: a verbatim move counts once.

## Blast radius and rollback
No runtime change (same functions, new paths; legacy stays the registered path). One git revert restores both trees. Merge deploys harmlessly. No config, terraform or env change.

## Verification
During TDD: ruff and the moved test files. At the end, from app/: make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, then once each, sequentially: full mypy, full pytest (tests --ignore=tests/smoke).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-20: implemented in the working tree on main ac8f8186 (the human creates stack-m/task-145.10.1-dissolve-scheduling with gh stack init; uncommitted work carries). Verbatim move (diff against HEAD: only module docstrings and imports changed): scheduling/adapters/google_calendar.py -> core/adapters/google_calendar.py; availability.py split into postmortem/domain.py (find_first_available_slot, get_utc_hour, identify_unavailable_users; imports get_federal_holidays from its own adapter) and postmortem/adapters/public_holidays.py (get_federal_holidays); scheduling/ deleted; modules/incident/schedule_retro.py imports repointed (legacy test patches the schedule_retro names, unchanged). Tests moved: unit/postmortem/test_incident_postmortem_slot_search.py, unit/core/test_incident_core_calendar_adapter.py, integration/postmortem/test_incident_postmortem_public_holidays_fetch.py (new __init__.py); test_incident_scheduling_boundaries.py deleted (its subject package is gone). Contract (i) is comms | postmortem | response | scribe; package_shape.txt scheduling entry deleted; test_seams_strict.txt three lines re-keyed (same patches, count 47 unchanged, header comment notes the re-key). ADR: incident-management.md :75 (calendar incident-owned in core/adapters, TASK-138 superseded), :137, :179 and a 2026-11-20 log entry; workplace-systems.md :70; features/incident/README.md core/postmortem rows, contract line, adapter-only rule, the calendar and retro routing rows (stale retrospective/ target row removed). Gates: ruff clean; make check-import-contracts 15 kept 0 broken; key ownership OK; package shape OK (2 baselined); test seams OK (47 strict, 12 legacy); mypy 40 errors in 13 files, none new (the two google_calendar.py errors are the moved verbatim lines); pytest tests --ignore=tests/smoke 8027 passed. One commit for the layer (squash-merged), not the two the plan sketched; the move stays reviewable as renames.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-20T22:06:00Z

---

2026-11-20: plan written to the approved TASK-145.10 rulings (verbatim move, no behaviour change); approved with them (human, 2026-11-20).

---
<!-- COMMENTS:END -->
