---
id: TASK-140.5
title: >-
  Draft an EN/FR public status update with /sre incident status-update in the
  scribe subdomain
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 19:08'
labels:
  - incident
dependencies:
  - TASK-140.3
  - TASK-140.4
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 324000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scribe use case: resolve the incident through core, read the transcript since the latest update's cutoff, and draft a structured update (stage, affected service, user impact, current action, workaround or no action needed, next update time ET) in EN and FR through the existing Summarizer with explicit structured instructions; answer parsing stays in scribe until TASK-134. Code, not the model, decides 'nothing new': no new human messages since the cutoff gives the prior update carried forward as 'no new information, next update by' with no model call; re-running while a draft is pending with nothing new returns that draft. Stages only move forward. The draft is stored as a draft record and shown privately to the responder.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With new channel activity, one model call produces EN and FR drafts with every field, stored as a draft record and shown only to the invoker
- [ ] #2 With no new human messages since the latest update, no model call is made and the prior update is carried forward with the no-new-information wording
- [ ] #3 Running it twice with nothing new returns the same pending draft and stores nothing new
- [ ] #4 A drafted stage earlier than the latest approved stage is raised to it
- [ ] #5 Outside an incident channel the command refuses with a localized message; all bot strings are in EN and FR catalogues
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 (TASK-140.1): the model fills structured fields only; text shown to the responder is rendered by the default comms profile (decisions/incident-management.md, External status updates), never by the prompt. The scribe Slack entry point uses native Bolt objects; the service imports no Slack SDK (platform-entrypoints.md rule 3).
<!-- SECTION:NOTES:END -->
