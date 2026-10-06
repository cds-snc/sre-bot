---
id: TASK-140.1
title: >-
  Record the external status update design in the incident and interaction
  decision records
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 17:43'
labels:
  - incident
dependencies:
  - TASK-110.2
parent_task_id: TASK-140
priority: high
type: docs
ordinal: 320000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Architecture only, no code. Amend decisions/incident-management.md: external status updates are a scribe use case; update records live under the incident id in core (record type, store interface); a StatusPagePublisher interface with a copy-ready default; the channel-to-incident lookup is core's find_incident_for_conversation, served for now by an adapter over the legacy incidents table until TASK-38.1's store replaces it. Accept the minimal part of decisions/interaction-toolkits.md (Draft) that packages need: registering Slack block actions and view submissions through a host-owned registrar, never the Bolt app.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/incident-management.md places external status updates, their records, the publisher interface and the interim lookup adapter, with a dated change-log line
- [ ] #2 decisions/interaction-toolkits.md (or a superseding record) accepts a minimal Slack action and view-submission registrar for packages, with its limits and tickets
- [ ] #3 Both records cite the 2026-10-06 research sources on status-update conventions and AI drafting with human approval
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Follow-up from TASK-139: when this ADR amendment lands, add a status-update row to the 'Where does new work go' table in app/packages/incident/README.md (and, once TASK-140.5 lands, a column in the scribe README's 'At a glance' table).
<!-- SECTION:NOTES:END -->
