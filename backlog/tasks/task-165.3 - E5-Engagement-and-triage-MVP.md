---
id: TASK-165.3
title: E5 Engagement and triage MVP
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-03T20:45:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.1
  - TASK-165.2
references:
  - decisions/incident-coordination.md
  - large-scale-incident-analysis.md
parent_task_id: TASK-165
type: feature
ordinal: 464000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deliver the first coordinated-incident workflow before workstreams or playbooks exist. A coordinator needs to engage products, collect explicit triage, and see an organisation-wide roll-up through Slack and the HTTP API. The flow must remain usable without GoAlert or standardized team groups: use the on-call port when configured and allow manual lead assignment otherwise.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A coordinator can engage, triage, reassign and disengage products through Slack and the HTTP API, with replay-safe behavior and stable identifiers.
- [ ] #2 Lead lookup uses only the on-call capability port when configured; without a source, the coordinator can assign a lead and the engagement records that it is unassigned until then.
- [ ] #3 The coordinating incident has a debounced Slack roll-up and receives durable engagement events through the outbox; integrations receive only neutral engagement intents.
- [ ] #4 Triage cards and deadlines support acknowledge, affected, not-affected with justification, reassignment, and escalation/reminder behavior.
- [ ] #5 Embargo can be set and lifted; every relevant read path returns 404 to non-members and notifications disclose only permitted minimum detail.
- [ ] #6 A scripted staging dry run demonstrates a CVE workflow end to end through Slack and the API; a full tabletop is optional.
- [ ] #7 The engagement and triage HTTP routes pass the TASK-163 edge test with no terraform change, and request bodies stay under the WAF Common Rule Set 8 KB body limit or a recorded scope-down decision covers them
<!-- AC:END -->
