---
id: TASK-165.5
title: E7 Workstreams and incident links
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-09T19:04:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-165.3
  - TASK-165.4
references:
  - decisions/incident-coordination.md
  - large-scale-incident-analysis.md
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 466000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend the MVP from one coordinating incident and engagement edges to a coherent incident workstream: typed links, creating or attaching child incidents, promotion, detach/merge, and resolution gating. The epic starts only after the G1 checkpoint in the delivery map; G1 requires a scripted dry run, while product-lead tabletop participation is optional.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Parent, related, and duplicate links are stored consistently on both incidents and repaired safely after partial failure.
- [ ] #2 An engagement can be fulfilled as a child incident after human confirmation; the child has an initial IncidentBinding (a place responders work it) and its progress is mirrored to the parent.
- [ ] #3 Promote, attach, detach, merge, and resolve-gating operations preserve authorization, embargo, and incident-link invariants.
- [ ] #4 Targeted tests exercise the supported link and workstream lifecycle, including repair and failure cases; the epic leaves no temporary parallel relationship model.
- [ ] #5 Fulfil moves an engagement's action items to the child, and every action item carries its root incident id, kept current by promote, attach, detach, and merge (D37), so references on the item (engagement, repository, later finding) follow the work.
- [ ] #6 Before adding root incident metadata, the approved plan specifies migration of existing items and typed relationship invariants across fulfil, attach, detach and merge. Lifecycle tests cover retries, preserved work/history and current visibility; changing a parent must not expose inaccessible items or leave unresolved references.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved, TASK-145.5.7 reconciliation): legacy and pre-coordination incidents carry no root metadata, and the TASK-145.5.7 legacy upgrade job is deleted by TASK-145.13 before doc-15 row 1 starts. AC6's plan for existing items therefore either reads absent root metadata as a standalone incident (its own root, no backfill, absent from any root index) or builds its own runner per decisions/incident-management.md Migration rule 3; it cannot extend the 145.5.7 job.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T18:37:00Z

---

Stack L OQ assessment 2026-11-09 (OQ10), proposed: the binding entity is renamed IncidentBinding (table sre_bot_incident_bindings) because 'surface' means a rebuilt legacy interaction group in migration.md and a message/modal/App Home in Slack; AC #2's 'working-surface binding' would read 'binding' once the human rules.

---
<!-- COMMENTS:END -->
