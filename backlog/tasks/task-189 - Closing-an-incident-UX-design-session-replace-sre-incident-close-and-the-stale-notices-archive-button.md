---
id: TASK-189
title: >-
  Closing an incident UX design session: replace /sre incident close and the
  stale notice's archive button
status: To Do
assignee: []
created_date: '2026-11-20T13:43:00Z'
updated_date: '2026-11-20T13:46:00Z'
labels:
  - incident
  - ux
  - design
dependencies: []
references:
  - decisions/incident-management.md
ordinal: 531000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-led design session (architecture mode, no code). /sre incident close and the stale notice's archive button were rebuilt as-is in response/ (TASK-145.8.5.3, archive_incident: find, join, change_status to Closed, archive the channel). Human 2026-11-20: the command's purpose is unclear and it is destructive when an inexperienced user runs it while the incident is still ongoing, so closing is designed afresh, not replicated; the command most likely goes away.

Evidence gathered 2026-11-20 (TASK-188 program-scope review): established tools keep the channel past resolution and archive it later, and archiving keeps it readable. PagerDuty archives by hand when the incident review is complete or 30 days after resolution, and keeps review discussion in the incident channel (pagerduty.com/eng/channels-are-free-why-we-gave-every-incident-its-own); FireHydrant archives at the Retrospective Completed milestone by default (docs.firehydrant.com/docs/runbook-step-archive-incident-channel); Rootly archives 24-48 h after Closed (docs.rootly.com/integrations/slack/workflows/archive-slack-channel); incident.io auto-archives 7, 14 or 28 days after close and runs a post-incident flow stage with its own tasks (docs.incident.io/incidents/lifecycle, incident.io/changelog/2022-01-10-auto-archive); Grafana one day after resolution with a warning; Jira Service Management after N days of inactivity, skipping channels linked to several incidents.

Gap in decisions/incident-management.md: when the conversation is archived relative to the postmortem is not decided. Today close archives at once, so postmortem's meeting post into the conversation is refused by conversation_is_writable (reading the transcript for draft should still work; verify that a bot can read an archived channel's history).

Questions for the session: who may close and what confirms it (a guard against closing an ongoing incident: status must be Resolved, a confirmation, a role); whether Closed is a status a person sets or the end of the postmortem stage; when and by what the conversation is archived (postmortem completed, a configurable delay as a typed setting per configuration.md, inactivity) and the warning before it; incidents with no postmortem; drills and verification incidents; what replaces the stale notice's archive button; whether /sre incident close is retired (migration.md step 4 retirement evidence: 90-day production usage) or kept as an explicit path; coordinated incidents (TASK-165: a parent closing with children open).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The closing flow is designed and approved by the human: who closes, the guard against closing an ongoing incident, and what Closed means relative to the postmortem
- [ ] #2 When and by what the conversation is archived is decided, with the warning and the case of an incident without a postmortem, and recorded in decisions/incident-management.md with cited practice
- [ ] #3 The fate of /sre incident close and the stale notice's archive button is decided with 90-day production usage evidence (migration.md step 4)
- [ ] #4 Implementation tasks are created or re-cut (the response archive service, the stale nudge in TASK-145.9.2 if affected, postmortem's meeting post) and placed in the doc-11 or doc-15 queue
- [ ] #5 Closing within a coordinated incident is designed: a parent with children still open, a child closing and its roll-up to the parent, and when each one's conversation is archived (TASK-165.5, TASK-165.3)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-20 (human): closing a standard incident already has implications; closing a parent or a child of a coordinated incident (TASK-165) is in this session's scope (AC #5); TASK-165.5 plans against its outcome.
<!-- SECTION:NOTES:END -->
