---
id: TASK-165.6
title: E3b Engagement scope and repositories
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
updated_date: '2026-11-04T16:12:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.1
  - TASK-165.4
references:
  - decisions/product-scope.md
  - decisions/incident-coordination.md
  - large-scale-incident-analysis.md
parent_task_id: TASK-165
type: feature
ordinal: 467000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend engagements from a product identifier to the assets and repository work needed by responders. At planning time resolve D33: Google Workspace is the primary IdP but does not yet have standard groups for teams and roles. Do not assume a team-to-people source; if the decision depends on an unavailable external source, deliver the person-level/catalogue behavior and leave group expansion to a separately planned epic.

Per-repository work is action items (D36, large-scale-incident-analysis.md §5.14): the asset keeps its triage hint and justification, while fix progress and its evidence live on the action items that reference the asset, so one repository can carry several fixes. This epic adds the optional repository reference to the core/ action item and a bulk action that creates one action item per affected asset of an engagement; E6b (TASK-165.10) adds the finding to the same bulk action.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Before implementation, the plan records a D33 decision for the source of team and role membership, its external dependencies, and a safe behavior if that source is not ready.
- [ ] #2 Engagements can target catalogue products and explicitly supported unowned or person targets without resolving owner-group identifiers into people.
- [ ] #3 Responders can propose and attach affected assets and select repositories for action items through the agreed workflow; per-repository fix progress is read from the asset's action items, never stored on the asset (D36).
- [ ] #4 Tracking issues created or linked from an embargoed incident preserve the confidentiality rule in the accepted product-catalog ADR.
- [ ] #5 If team membership depends on an unavailable external source, the epic closes whole with person-level targets and no group-expansion fallback; follow-on group resolution is a separate epic.
- [ ] #6 A bulk action creates one action item per affected asset of an engagement, previewed and confirmed by a person, never automatic; replays create no duplicates.
<!-- AC:END -->
