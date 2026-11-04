---
id: TASK-165.7
title: E8 Reporting and communication audiences
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
updated_date: '2026-11-04T16:45:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.3
  - TASK-147
references:
  - decisions/incident-coordination.md
  - large-scale-incident-analysis.md
parent_task_id: TASK-165
type: feature
ordinal: 468000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinators need audience-specific updates, senior-management summaries, metrics, and one organisation-level postmortem that takes each workstream’s timeline and lessons as inputs. Audience membership is uncertain because standard Google Workspace product-team and role groups do not yet exist; resolve D33 at planning and use a reviewed explicit person list until a reliable source is accepted. Finding names the issues a report brings (E6b, TASK-165.10); postmortem contributions are called workstream inputs. E8 delivers reporting independently of findings. E6b follows this epic and owns integrating per-finding progress into these reporting surfaces, so that integration is not an implicit dependency or untracked follow-up here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Coordination and senior-management audiences have distinct, authorized update paths and a reminder for the executive summary.
- [ ] #2 An umbrella incident can produce per-product external updates without disclosing information about other products.
- [ ] #3 Coordination metrics describe the agreed lifecycle and response measures without exposing embargoed content.
- [ ] #4 The organisation-level postmortem consumes each workstream's timeline and lessons as inputs through the postmortem capability after TASK-147.
- [ ] #5 D33 determines audience membership; until an accepted source is available, membership is configured as explicit people and never inferred from unstandardized groups.
<!-- AC:END -->
