---
id: TASK-165.10
title: 'E6b Findings: many issues in one coordinated incident'
status: To Do
assignee: []
created_date: '2026-11-04T16:12:00Z'
updated_date: '2026-11-04T16:45:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.4
  - TASK-165.5
  - TASK-165.6
  - TASK-165.7
references:
  - large-scale-incident-analysis.md
  - decisions/incident-coordination.md
  - decisions/incident-management.md
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 476000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A vulnerability disclosure program (VDP), pentest report or advisory batch may bring many findings across products and repositories. Coordinate the report as one incident rather than requiring one incident per vulnerability. Findings remain optional: a single-issue incident works without them.

The proposed finding carries a short title, source reference, source rating, validation and reason, remediation deadline and optional disclosure date. Details stay in the source system; findings are not a vulnerability register and do not import scanner alerts. Use typed optional finding references on the shared core/ action item, not another task record. Root-scoped reads must handle pagination, eventual index consistency and current visibility. The approved plan settles status aggregation, existing-record migration, and how links survive fulfil, attach, detach and merge without losing history or leaking access (D35-D38).

coordination/ owns this behavior; shared records/contracts follow decisions/feature-packages.md. The G1 walkthrough feeds the approved scenario matrix and behavior tests. This epic follows workstreams (TASK-165.5), repository scope (TASK-165.6) and reporting (TASK-165.7), and owns adding finding progress to the existing reporting surfaces. E8 does not depend on findings. Decompose this outcome into reviewable implementation tasks when it is next.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Findings can be created, validated, updated, and listed through the API and Slack, one at a time or in bulk from a pasted list, each with an external reference to its source and no copy of the report.
- [ ] #2 An action item can reference one finding, and the per-asset bulk action from E3b can create one action item per affected asset for a finding, previewed and confirmed by a person.
- [ ] #3 The root-scoped roll-up lists each finding’s engagements, repositories and action items, overdue first, without scanning all incidents. Tests cover pagination, index lag, current visibility and relationship changes through fulfil, attach, detach and merge; stale index data never authorizes access or resolves an incident.
- [ ] #4 Under embargo a finding’s title follows the minimum-detail rule; disclosure and remediation dates are reminded to the coordinator by a leased job and never published or acted on automatically.
- [ ] #5 The existing E8 senior-management summary and coordination metrics include per-finding progress (time to validate and time to remediate against the due date) when findings exist, and retain engagement-only reporting otherwise.
- [ ] #6 A scripted staging VDP dry run (one report, several findings across several products and repositories) completes end to end through Slack with API parity. Evidence is retained in the task: one finding across multiple repositories, multiple findings on the same repository, missing ownership, partial completion, and no-finding incidents. Partial or absent remediation evidence must not be reported as fully fixed.
- [ ] #7 The approved plan retains the reviewed scenario/cardinality matrix and typed-reference invariants. Behavior tests preserve old action items without finding references, separate the progress of different findings on the same repository, and preserve item identity/history when response work becomes follow-up work.
<!-- AC:END -->
