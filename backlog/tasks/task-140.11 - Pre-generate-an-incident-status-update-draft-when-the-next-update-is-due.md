---
id: TASK-140.11
title: Pre-generate an incident status-update draft when the next update is due
status: To Do
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-07 18:52'
labels:
  - incident
dependencies:
  - TASK-140.6
  - TASK-140.10
parent_task_id: TASK-140
priority: low
type: feature
ordinal: 335000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Idea from 2026-10-07 review: when an approved update's next update time approaches, the scribe prepares a fresh draft so responders find one ready, in addition to drafting on demand with the Draft button. This also answers stale next-update times on drafts reviewed long after drafting. Security incidents and incidents with an unknown security flag are never drafted automatically: only a manual Draft with confirmation drafts them (TASK-140.10). Scope, trigger mechanism and notification are to be decided when this is planned.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A draft is prepared ahead of the next update time for non-security incidents with an approved update
- [ ] #2 Security and unknown-flag incidents are never drafted automatically
- [ ] #3 No message is posted to the incident channel; the draft appears in the status-updates modal
<!-- AC:END -->
