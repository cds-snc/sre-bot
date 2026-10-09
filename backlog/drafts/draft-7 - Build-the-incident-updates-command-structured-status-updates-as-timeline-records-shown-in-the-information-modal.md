---
id: DRAFT-7
title: >-
  Build the incident updates command: structured status updates as timeline
  records, shown in the information modal
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-145.13
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2). /sre incident updates is registered today (modules/incident/incident_helper.py:408): add opens a modal and show lists the free-text updates, stored by reading the item and rewriting its incident_updates list (modules/incident/incident_folder.py); two incidents have ever used it, and TASK-140 retires it. This task builds internal updates on the record: an update is a timeline record with author, time and text, posted to the conversation when writable, appended to the report, and listed in the information modal. Scribe's summarize may later read these records as a higher-signal source than the raw transcript.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An update is stored as its own record under the incident and never as a list attribute
- [ ] #2 Updates render in the information modal and in the report in EN and FR
- [ ] #3 The command works on an incident whose channel is archived, skipping the channel post
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06: overlaps TASK-140. External public status updates are stored as StatusUpdate records under the incident id (TASK-140.4) and the legacy updates command is retired by TASK-140.7. If this draft is promoted, it should cover internal timeline updates only and read TASK-140's records for the information-modal history rather than adding a second update store.
<!-- SECTION:NOTES:END -->
