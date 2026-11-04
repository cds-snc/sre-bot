---
id: TASK-165.4
title: E6 In-incident action items
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-04T16:44:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.3
  - TASK-147.2
references:
  - decisions/incident-coordination.md
  - large-scale-incident-analysis.md
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 465000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Once the engagement-and-triage MVP is usable, incident teams need a shared list of response action items for work that does not yet justify a separate repository integration. They are the same record as postmortem follow-ups (decisions/incident-management.md, amended 2026-11-04): the ActionItem record and its store in core/ (TASK-147.2) with kind response, so this epic adds no task record of its own. response/ owns the response kind's API and Slack surfaces and its reminder job, which reads only the response partitions of the shared due index. An item can reference its owning engagement, is required or not applicable with a reason, and can become a follow-up by changing its kind. Items must work in the API and Slack and remain distinguishable from workstream engagements.

Tracking issues reuse the core/ GitHub adapter (TASK-147.4) and status sync (TASK-147.5) when they exist. If the postmortem-records flag still gates the sync handler when this epic starts, the plan decides how response items receive issue status without turning on the postmortem surfaces. The repository reference is added by E3b (TASK-165.6) and the finding reference by E6b (TASK-165.10).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Response action items can be created, updated, assigned, and marked not applicable with a reason through the API, on the shared core/ action-item store with kind response; no separate task record exists.
- [ ] #2 Slack provides action-item views and actions consistent with the API behavior.
- [ ] #3 Response reminders are registered by response/, read only the response partitions of the due index, use the shared job/lease patterns, and do not duplicate or silently drop notifications.
- [ ] #4 An open response item can become a follow-up by changing its kind, keeping its owner, issue reference, and history.
- [ ] #5 Targeted tests cover lifecycle, not-applicable reasons, kind change, permissions, and reminder behavior.
- [ ] #6 Adding response behavior preserves existing follow-up records without coordination references. Tests verify kind changes retain item identity and history, update the correct due-index partition, and neither skip reminders nor send both kinds of reminder. Unsupported kinds and transitions are rejected.
<!-- AC:END -->
