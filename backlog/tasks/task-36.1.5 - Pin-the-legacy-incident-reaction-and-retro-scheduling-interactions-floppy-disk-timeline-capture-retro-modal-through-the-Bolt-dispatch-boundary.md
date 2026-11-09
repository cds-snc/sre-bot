---
id: TASK-36.1.5
title: >-
  Pin the legacy incident reaction and retro-scheduling interactions
  (floppy-disk timeline capture, retro modal) through the Bolt dispatch boundary
status: Done
assignee: []
created_date: '2026-11-06T19:04:00Z'
updated_date: '2026-11-09T17:44:00Z'
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
- [x] #1 Each of the 7 interaction rows has a dispatch-driven test covering ack, Slack-visible calls and outcomes at the faked edges; modal-internal ids are read from the opened view, never hard-coded
- [x] #2 INVENTORY.md marks these rows pinned by this task, with target incident.response (reactions) or incident.postmortem (retro) and rebuild ticket TASK-145.9 or TASK-145.10
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #4 Pins follow decisions/testing.md seams during the legacy migration: fakes at external edges, any internal legacy seam only in a named legacy_surface/conftest.py fixture naming its owning rebuild task
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-grounded 2026-11-06 at pickup against main 929e6c3c, and re-checked against main 7b0b3810 after #1834 (TASK-186) and #1835 (TASK-187) merged. The plan's paths are unchanged. Supersedes the plan carried from TASK-36.1.2 (grounded at 76f73bde). Test-only, 0 production LOC. Follows the pin contract in decisions/migration.md and the seam rules in decisions/testing.md (TASK-36.1.2 OQ6; TASK-187 rulings).

## What changed from the carried plan (needs approval)
- C1 Fakes move to the Google edge; no new internal seam. The carried step 1 faked features.incident.core.adapters.google_docs and features.incident.scheduling.adapters.google_calendar at module level. Under TASK-187 those are internal seams. Both modules build their clients through integrations.google_workspace.client._build_service, which incident_surface already fakes (FakeGoogleWorkspace.service(api_name)). Instead: FakeDocsDocuments gains get (body.content paragraphs with start/end indexes, revisionId) and a structural batchUpdate (deleteContentRange, insertText, writeControl.requiredRevisionId; stale revision -> HttpError 400). FakeGoogleWorkspace gains a "calendar" service: freebusy().query (busy calendars configurable, empty by default) and events().insert (records the body, returns htmlLink). Result: zero new seam fixtures and zero entries in test_seams_legacy.txt. The migration.md rule 3 expand-step exception is not used.
- C2 Federal holidays: availability.get_federal_holidays calls https://canada-holidays.ca through requests.get, an external edge. Faked in the retro test module by patching get on the requests module itself (the guard resolves it to requests, outside its guarded roots). Never patch it through a features.incident.scheduling.availability path, which resolves into features/ and fails. It returns an empty holiday list, so no network.
- C3 Guard: TASK-187 is on main; make check-test-seams runs normally on the branch and must report no net-new legacy pin seams (12 baselined). Nothing to re-key. Its CI passes only after main's strict-zone comms entries are re-keyed (the TASK-186/187 merge-order gap, outside this task).
- C4 Comms: untouched (TASK-186's moves are irrelevant to these rows).

## Rows and owners (unchanged; lines verified on main)
- TASK-145.9 (incident.response): reaction_added and reaction_removed. The floppy-disk matcher is at incident_helper.py:160-161 and the ack-only fallback at 162-163. Event types are durable; no ids.
- TASK-145.10 (incident.postmortem): view_save_event (156, schedule_retro.py:237), confirm_click (157, :346), user_select_action (158, :364). Modal-internal: /sre incident schedule opens the modal (handle_schedule -> open_incident_retro_modal); ids are read from the opened view.

## Steps
1. conftest.py (additive): the C1 Docs and Calendar fakes in FakeGoogleWorkspace; a helper that seeds an incident report document with the Timeline headings, and an "Incident report" bookmark on the incident channel (the legacy document id comes from bookmarks_list).
2. test_incident_conversation_reaction_surface.py (4 rows, via the harness's event()):
   - Floppy disk on a message in an incident- channel appends exactly one timeline entry (permalink, real name, ET time).
   - Re-adding it changes nothing (no batchUpdate).
   - Removing it deletes the entry.
   - Other emoji, or a non-incident channel: ack only. For other emoji, zero Web API calls and the matcher listener does not run (proves Bolt runs only the first matching listener).
   - A stale revision on the first write retries from a fresh snapshot.
3. test_incident_retro_schedule_surface.py (3 rows): /sre incident schedule in an incident channel opens the modal. user_select_action through read ids updates the view, and listing a busy user shows the unavailable warning. confirm_click acks. view_save_event creates one calendar event "Retro <name>" with the selected attendees' emails on the postmortem calendar_id and posts the confirmation with the link. Failure paths: no free slot (all busy) and an insert failure show the failure view. The first slot is asserted by invariants (weekday, inside business hours, after now + days); time is not frozen.
4. INVENTORY.md: the 7 rows get Pinned by TASK-36.1.5, real Defined at lines, Target (incident.response / incident.postmortem) and Rebuild ticket (145.9 / 145.10), replacing "TASK-38 (after TASK-97)".
5. Mutation-check each file once (break the matcher, drop the attendees).

## Seams (AC #4)
New internal seams: none. Existing seams reused: none required (incident_surface and routed_slack_client fake only edges). If implementation finds a call that the edges cannot reach, stop and name it here before adding a fixture. Its owner would be TASK-145.9 (reactions) or TASK-145.10 (retro), with its '<fixture>::<target>  # TASK-<id>' baseline entry in this PR.

## Doubts (verify during TDD)
- The postmortem settings slice must give calendar_id in tests (settings getter, sanctioned). Use the existing settings override if the conftest already has one.
- find_first_available_slot uses utcnow and local hours: assert invariants only.

## Verification (from app/)
During work: uv run ruff check . and the two files. At the end, once each and in order: full mypy, then uv run pytest tests --ignore=tests/smoke; make check-import-contracts, make check-settings-key-ownership, make check-package-shape, make check-test-seams.

## Size
0 production. 2 new test files + conftest + INVENTORY (4 files, ~650 test LOC; the Docs fake adds ~100). Passes the gate. Domain-model gate n/a (no entity change). Blast radius: tests only; one git revert.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-11-06 from main 7b0b3810 (re-grounded plan C1-C3 approved). Tests only, 0 production LOC.
- conftest.py (additive): the Docs fake now models paragraphs, text runs with links, 1-based indexes and revisions (get; batchUpdate with deleteContentRange, insertText, link updateTextStyle and the requiredRevisionId guard, a stale revision answered 400; concurrent_edits simulates another editor); a Calendar fake (freebusy.query with fully_busy calendars, events.insert, insert_error) behind the same _build_service edge; add_timeline_report, google_http_error, number_input answers.
- tests/factories/slack_bolt.py: FakeSlackClient replies may be functions of the request arguments (per-user and per-message lookups).
- test_incident_conversation_reaction_surface.py (10 tests, 4 rows) and test_incident_retro_schedule_surface.py (9 tests, 3 rows); INVENTORY rows repointed to 145.9 / 145.10 with real lines.
- Seams: none added. check-test-seams OK (47 strict, 12 legacy). Holidays faked by patching get on the requests module.
- Mutation checks caught: matcher matching everything, no chronological sort, removal no-op, dedupe dropped, no retry, attendees dropped, bot not excluded, warning dropped, no announcement. Weekend skipping is date-dependent (invariant assert only).
- Legacy behaviour pinned as is (noted on 145.9 and 145.10): a refused calendar insert escapes the submit handler and leaves the loading view (the 'no link' failure branch is unreachable: insert_event raises, never returns None); timeline errors are logged and swallowed.
- Gates: ruff clean; contracts 13 kept; key ownership OK; package shape OK (3 baselined); seams OK; mypy 41 pre-existing (none in touched files); pytest 6562 passed.
<!-- SECTION:NOTES:END -->
