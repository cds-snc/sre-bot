---
id: TASK-145.9
title: >-
  Rebuild timeline capture and the stale-channel nudge in incident/response;
  summarize moves in; incident leaves aws_platform
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:22'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8
  - TASK-36.3
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 359000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C3 of TASK-145. Rebuilds the floppy-disk reaction handlers (message captured into the report's timeline and the record's timeline entries; removal deletes both), the ack-only reaction fallbacks and the stale-channel nudge job, moves /sre incident summarize from scribe into response, and deletes modules/incident/db_operations.py.

THIS SLICE
- Timeline capture through IncidentReport and IncidentStore; entries are their own records.
- The nudge job is registered by response through the background-job hookimpl with its schedule and lease from the response settings slice; the hand import in app/jobs/scheduled_tasks.py is deleted. Stale detection reads the store, not a channel-name pattern; the nudge carries the archive action id and the schedule-postmortem action id from common/vocabulary.
- summarize: scribe/service.py's summary path becomes response/summary.py with its settings slice, catalogue (incident_summary) and tests renamed test_incident_response_summary_*; the command registers under incident.response. It calls the Summarizer directly until TASK-25.10.
- After this slice no module under app/modules/incident imports db_operations or packages.aws_platform; the incident seam baseline entries are removed, which is what TASK-88 needs.
- Legacy registrations and the job hand import removed in the same PR; pinned by TASK-36.1 (reactions) and TASK-36.3 (job).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Floppy-disk capture and removal write and delete timeline records and report entries through core; the legacy handlers are gone
- [ ] #2 The stale-channel job is registered by response through the hookimpl and reads the store; app/jobs/scheduled_tasks.py no longer imports it
- [ ] #3 /sre incident summarize is handled by response/summary.py and scribe no longer holds a summary path, catalogue or test
- [ ] #4 No module imports modules.incident.db_operations or packages.aws_platform for incident data; the incident seam baseline entries are removed
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.8 and TASK-36.3). doc-2 forbids mixing a mechanical move with a behaviour change in one layer, so this task is delivered as TASK-145.9.1 (rebuild: timeline capture, nudge job, aws_platform exit) and TASK-145.9.2 (mechanical: summarize moves into response), human decision before implementation.

## Discovered state
- Timeline: modules/incident/incident_conversation.py handle_reaction_added (264) and handle_reaction_removed (325) with the floppy-disk matcher (incident_helper.py 162-165), calling incident_document.update_timeline_section (84-200: extraction 134, headings 171, replacement 187); db_operations.log_activity (164) appends with list_append. Nudge: notify_stale_incident_channels.py (50) posts with an archive button (callback archive_channel); hand-imported by jobs/scheduled_tasks.py:109 ("scheduler:notify_stale_incident_channels"). aws_platform: db_operations.py imports packages.aws_platform.adapters.dynamodb (233 lines, all incident data access).
- Summarize: scribe/service.py summary path (functions around summarize, settings IncidentSummarySettings, catalogue incident_summary.*, tests test_incident_scribe_summary_{service,slack,settings,locales}.py, test_incident_scribe_conversation_summarize.py), handler handle_summarize_command (entrypoints/slack.py 317-370).

## Steps
TASK-145.9.1
1. core/store.py: append_timeline_entry(entry) as its own record (conditional put) and delete_timeline_entry; list_timeline; fake. Store test proves no list_append and no get-then-put.
2. response/service.py: capture_message (IncidentReport.append_timeline_entry plus store append), uncapture (both removed), stale_incidents (store list where no timeline or status change within the window). response/entrypoints: reaction_added and reaction_removed listeners with the matcher, registered through the registrar's event support (verify the registrar exposes events; TASK-26.1 contract); the nudge job registered through the background-job hookimpl with schedule and lease from the response settings slice; the nudge carries the archive and schedule-postmortem action ids from common/vocabulary.
3. Delete modules/incident/db_operations.py, notify_stale_incident_channels.py and the jobs/scheduled_tasks.py import; remove the incident seam baseline entries; legacy registrations removed; pinned by TASK-36.1 (reactions) and TASK-36.3 (job).
TASK-145.9.2
4. `git mv` the summary path into response/summary.py (service), its settings class into response/settings.py, the catalogue into response/locales, tests renamed test_incident_response_summary_*; the command registers under incident.response; scribe keeps draft only. The Summarizer import moves with it (ignore entry renamed, not added) until TASK-25.10.

## AC traceability
AC1: steps 1-2 -> capture tests. AC2: step 2 -> job registration test; `rg notify_stale jobs/` empty. AC3: step 4 -> summary tests under response; `rg summar features/incident/scribe` empty. AC4: step 3 -> `rg 'aws_platform|db_operations' app/modules/incident` empty; baseline diff. AC5: gates.

## Test matrix
Capture: reaction on a message in an incident channel -> record and report entry; removal deletes both; reaction in a non-incident channel ignored; report failure leaves the record entry and reports. Nudge: stale detection window; safe to run twice; buttons carry the shared ids. Summarize: unchanged behaviour under new paths.

## Assumptions and doubts
- The Slack registrar contract may not expose event listeners yet (TASK-26.1 defined commands, actions and views); if so, the reactions register through the hookspec that TASK-140.2 added or a small contract extension lands first as its own PR.
- TASK-88 waits for this slice's aws_platform exit.

## Size
9.1 about 350 production lines; 9.2 a move of about 450 lines with no new code.

## Blast radius and rollback
The nudge job and the reactions are low-traffic; the aws_platform deletion is the riskiest step and reverts with the PR.
<!-- SECTION:PLAN:END -->
