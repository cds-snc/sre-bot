---
id: TASK-165.9
title: E10b Managed playbooks and administration
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
labels:
  - incident
  - content
milestone: m-7
dependencies:
  - TASK-165.8
  - TASK-178
references:
  - decisions/managed-content.md
  - decisions/organisation-content.md
  - decisions/provisioned-content.md
parent_task_id: TASK-165
type: feature
ordinal: 471000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add managed in-flight playbook edits only after the provisioned pilot and shared managed-content path are delivered and a team needs this capability. Keep one validated, authorized, versioned and audited write path, and preserve round-trip compatibility with provisioned content.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Authorized users can create, revise, and retire playbooks through the agreed admin surface using the shared managed-content write path.
- [ ] #2 Playbook versions and audit events are retained, and the per-kind kill switch is honored.
- [ ] #3 Managed playbooks export to the provisioned format and pass the shared compatibility checks.
- [ ] #4 TASK-165 playbook acceptance is complete across the provisioned pilot and managed administration without a parallel or bypass write path.
<!-- AC:END -->
