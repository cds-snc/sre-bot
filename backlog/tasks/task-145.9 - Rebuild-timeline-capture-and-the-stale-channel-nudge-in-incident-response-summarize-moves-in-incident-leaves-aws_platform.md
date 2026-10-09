---
id: TASK-145.9
title: >-
  Rebuild timeline capture and the stale-channel nudge in incident/response;
  summarize moves in; incident leaves aws_platform
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
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
