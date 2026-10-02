---
id: DRAFT-7
title: >-
  Build the incident updates command: structured status updates as timeline
  records, shown in the information modal
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-38.8
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2). /sre incident updates is registered today (modules/incident/incident_helper.py:408) with its view deferred, and the record's incident_updates field is unused. This task builds it on the record: an update is a timeline record with author, time and text, posted to the conversation when writable, appended to the report, and listed in the information modal. Scribe's summarize may later read these records as a higher-signal source than the raw transcript.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An update is stored as its own record under the incident and never as a list attribute
- [ ] #2 Updates render in the information modal and in the report in EN and FR
- [ ] #3 The command works on an incident whose channel is archived, skipping the channel post
<!-- AC:END -->
