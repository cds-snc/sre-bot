---
id: TASK-36.1.5
title: >-
  Pin the legacy incident reaction and retro-scheduling interactions
  (floppy-disk timeline capture, retro modal) through the Bolt dispatch boundary
status: To Do
assignee: []
created_date: '2026-11-06T19:04:00Z'
updated_date: '2026-11-06T19:12:00Z'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36.1.1
parent_task_id: TASK-36.1
priority: medium
ordinal: 490000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split from TASK-36.1.2 on 2026-11-06 (human-approved OQ3). Pins the 7 incident_helper.py interactions that TASK-145.9 and TASK-145.10 replace: events reaction_added and reaction_removed, each as the floppy-disk matcher and the ack-only fallback (TASK-145.9, incident.response timeline capture); view_save_event, confirm_click and user_select_action (TASK-145.10, incident.postmortem). Follows the pin contract recorded in TASK-36.1.2 and decisions/migration.md: durable entry points only (event types; /sre incident schedule opens the retro modal and its ids are read from the opened view), Slack-visible output and domain outcomes at external edges (one timeline entry in the report, one calendar event with its attendees).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 7 interaction rows has a dispatch-driven test covering ack, Slack-visible calls and outcomes at the faked edges; modal-internal ids are read from the opened view, never hard-coded
- [ ] #2 INVENTORY.md marks these rows pinned by this task, with target incident.response (reactions) or incident.postmortem (retro) and rebuild ticket TASK-145.9 or TASK-145.10
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #4 Pins follow decisions/testing.md seams during the legacy migration: fakes at external edges, any internal legacy seam only in a named legacy_surface/conftest.py fixture naming its owning rebuild task
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Carried from the TASK-36.1.2 plan reviewed 2026-11-06 (split approved by the human, OQ3); grounded at main 76f73bde, re-ground at pickup. Test-only, 0 production LOC. Follows the pin contract in decisions/migration.md (2026-11-06) and the test-seam rule TASK-36.1.2 OQ6 settles. Lands after TASK-36.1.2 (shares its conftest fixtures and the view-driven interaction helper); gates TASK-145.9 and TASK-145.10.

## Rows and owners
- TASK-145.9 (incident.response): reaction_added and reaction_removed, floppy-disk matcher (incident_helper.py:160-161) and ack-only fallback (162-163). Event types are durable; no ids.
- TASK-145.10 (incident.postmortem): view_save_event (156, schedule_retro.py:237), confirm_click (157, schedule_retro.py:346), user_select_action (158, schedule_retro.py:364). Modal-internal: opened by /sre incident schedule, ids read from the view.

## Steps
1. conftest.py (additive): the Google document fake gains a timeline section (in-memory text, at features.incident.core.adapters.google_docs); calendar fake at features.incident.scheduling.adapters.google_calendar (get_freebusy, insert_event) returning an empty busy list and an event link.
2. test_incident_conversation_reaction_surface.py (4 rows): floppy-disk in an incident- channel appends exactly one timeline entry in the fake document; re-add no-op; removal deletes it; other channels and other emoji: ack only, zero Web API calls; matcher runs first.
3. test_incident_retro_schedule_surface.py (3 rows): /sre incident schedule opens the modal; user selection and submit through read ids; one calendar event "Retro <name>" with attendees and the confirmation message; no free slot or insert failure shows the failure view; first slot asserted by invariants (utcnow).
4. INVENTORY.md: the 7 rows get Pinned by, real Defined at lines, Target (incident.response / incident.postmortem) and Rebuild ticket (145.9 / 145.10), replacing "TASK-38 (after TASK-97)".
5. Mutation-check each file once.

## Doubts (verify at pickup)
- Bolt runs only the first matching event listener (the first reaction test proves it).
- schedule_event reads datetime.utcnow and federal holidays: assert invariants, do not freeze time.

## Verification (from app/)
During work: uv run ruff check . and the two files. At the end, once each, sequentially: full mypy, then uv run pytest tests --ignore=tests/smoke; make check-import-contracts, make check-settings-key-ownership, make check-package-shape.

## Size
0 production; 2 new test files + conftest + INVENTORY (4 files, ~550 test LOC). Blast radius: tests only, one git revert.
<!-- SECTION:PLAN:END -->
