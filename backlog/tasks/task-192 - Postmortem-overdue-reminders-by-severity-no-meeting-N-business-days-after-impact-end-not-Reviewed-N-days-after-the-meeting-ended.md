---
id: TASK-192
title: >-
  Postmortem overdue reminders by severity: no meeting N business days after
  impact end, not Reviewed N days after the meeting ended
status: To Do
assignee: []
created_date: '2026-11-20T22:05:00Z'
labels:
  - incident
  - postmortem
dependencies:
  - TASK-147.2
  - TASK-189
priority: low
type: feature
ordinal: 539000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-11-20 (human, TASK-145.10 post-meeting lifecycle design): industry tools nudge an overdue postmortem (PagerDuty: meeting within 3 calendar days for SEV-1, 5 business days for SEV-2; Atlassian: review within five business days; incident.io: due dates by severity with one reminder). The meeting state is derived from the calendar event (TASK-145.10.6); the review stages are IncidentStatus Ready to be Reviewed -> Reviewed (TASK-147.7).

Scope: a leased scheduled job (reliability.md, TASK-64) posts a bilingual reminder in the incident conversation (and to the postmortem owner) when (a) no postmortem meeting exists N business days after impact end, or (b) the incident is not Reviewed N days after the meeting ended; N per severity as typed settings; skipped for an incident that opted out of a postmortem (TASK-147.1) or is Closed (TASK-189). A cross-incident query by meeting time may need an additive index (decide at planning).

Sources: https://docs.pagerduty.com/ops-guides/incident-response-guide/postmortem-process, https://support.atlassian.com/jira-service-management-cloud/docs/post-incident-review-best-practices/, https://docs.incident.io/post-incident/due-dates
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A leased job reminds once per condition: no meeting N business days after impact end; not Reviewed N days after the meeting ended; N per severity as typed settings
- [ ] #2 Opted-out and Closed incidents are skipped; reminders are bilingual in the incident conversation
- [ ] #3 incident-management.md Postmortem records the overdue rule
<!-- AC:END -->
