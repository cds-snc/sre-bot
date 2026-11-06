---
id: TASK-165.2
title: E4 Coordination foundations
status: To Do
assignee: []
created_date: '2026-11-03T18:58:00Z'
updated_date: '2026-11-06T02:59:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-145
  - TASK-34
  - TASK-83.4
references:
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 463000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinated incidents need a stable service and authorization foundation before engagements can be enabled: a coordination ADR, incident HTTP API, member and engagement records, and a person-based roster. The atomic-record-write/outbox work remains tracked by TASK-34, and E4 uses the people capability from TASK-83.4. The coordination model must not depend on Google group membership being standardized.

The coordination ADR records the work model proposed in large-scale-incident-analysis.md section 5.14, on top of the shared action-item type decided in decisions/incident-management.md (D34): optional findings with an external reference, never a vulnerability register (D35); per-repository fix progress on action items (D36); items on the incident doing the work with root-scoped reporting and preserved ownership/visibility (D37); incident-wide embargo and tracked disclosure dates, never automatic publication (D38). Store the reviewed scenario/cardinality matrix, assumptions and migration questions in the approved task plan. The G1 VDP walk-through can amend these before E6 starts; a pivot must update affected ADRs, consumer tasks, dependencies and delivery maps before implementation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The coordination decisions are recorded in a new decisions/incident-coordination.md, with required riders to reliability.md, authorization.md, errors-and-http.md, and feature-packages.md.
- [ ] #2 An incident HTTP API base exposes incident read/list operations with the repository error mapping and caller identity boundaries.
- [ ] #3 Member and engagement persistence is available through typed contracts and fakes, with no cross-domain concrete infrastructure imports.
- [ ] #4 A person-based roster supports role-derived and manually added members, and every incident read path enforces the visibility policy; authorization does not expand IdP or platform groups.
- [ ] #5 Atomic multi-item writes and the outbox relay are usable by coordination through TASK-34, and targeted tests cover success, authorization, embargo visibility, and error mapping.
- [ ] #6 The incident HTTP API routes pass the TASK-163 edge test with no terraform change (under /api/v1/, authenticated by get_current_user unless public by decision); if this is the first authenticated /api/v1 route live in production, deploy-checks post edge runs with a Backstage token (bad token 401 with WWW-Authenticate: Bearer, valid token outside 401/403); POST bodies over 8 KB are blocked by the WAF Common Rule Set outside /hook/, so the API sizes requests under it or the epic records a scope-down decision
- [ ] #7 decisions/incident-coordination.md records D35–D38 (findings as optional records with an external reference and never a register, per-repository progress on action items, where action items live with the root incident id, incident-wide embargo with tracked disclosure dates) and adds no task or action-item record type beside the core/ one.
- [ ] #8 The approved task plan retains a human-reviewed six-scenario cardinality matrix (CVE, credentials, platform outage, vendor, privacy, VDP/pentest report), including many issues across many teams/repositories and products with no repository. The ADR records ownership, lifecycle and visibility invariants; exhaustive field lists stay in plans/code. Behavioral tests cover the foundation cases introduced here, with later cases assigned to their owning epics.
- [ ] #9 The incident API distinguishes explicitly extensible classification/display values from closed lifecycle and authorization values. Contract tests preserve existing records/responses, reject unsupported commands and transitions, and never grant access for unknown values. Unknown read classifications must remain visibly unknown, not become success states; surface tasks inherit that compatibility requirement.
- [ ] #10 If app/bin/baselines/package_shape.txt still holds the people capability's readme-consumers entry, it is deleted and the capability README names this consumer
<!-- AC:END -->
