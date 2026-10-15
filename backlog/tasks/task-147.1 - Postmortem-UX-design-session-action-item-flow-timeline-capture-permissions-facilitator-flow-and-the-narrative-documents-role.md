---
id: TASK-147.1
title: >-
  Postmortem UX design session: action-item flow, timeline capture permissions,
  facilitator flow and the narrative document's role
status: To Do
assignee: []
created_date: '2026-10-13 14:00'
updated_date: '2026-10-15 17:52'
labels:
  - incident
  - features
dependencies: []
references:
  - 'https://github.com/cds-snc/sre-bot/issues/1706'
parent_task_id: TASK-147
priority: high
type: feature
ordinal: 370000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-led design session, run in parallel with the backend slices (TASK-147.2). Output is a backlog doc that the slices with user-facing surfaces plan against.

Questions to settle:
- Action items: how they are added, confirmed, edited, assigned and prioritised from Slack (Teams later); how AI-proposed items from the transcript are reviewed; how the GitHub issue is created and what the item shows afterwards; reminders and their cadence; what the facilitator sees across incidents.
- Timeline capture: who may capture a message with the floppy-disk reaction (any channel member, or the incident roles only), who may remove an entry, and whether the reaction stays the trigger.
- The narrative document: template and sections, how the read-only facts and action items appear in it, and what marking the review complete does.
- EN/FR wording and WCAG for every surface; the flag-on experience compared with today's, as input to the rollout comms (TASK-147.8).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A backlog doc records the decided action-item, timeline-capture and narrative-document flows, with the capture and removal permission rule
- [ ] #2 The doc lists the user-facing surfaces each later slice builds, with EN/FR wording owners
<!-- AC:END -->
