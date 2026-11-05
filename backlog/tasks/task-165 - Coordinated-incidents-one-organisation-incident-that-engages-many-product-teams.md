---
id: TASK-165
title: >-
  Coordinated incidents: one organisation incident that engages many product
  teams
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
updated_date: '2026-11-05T15:54:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-145
  - TASK-167
references:
  - backlog/docs/doc-15 - Coordinated-incidents-delivery-map.md
type: feature
ordinal: 437000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: this is the parent for coordinated-incident work only. The GoAlert on-call/paging work (TASK-146) and cloud investigations (TASK-179) are sibling work items, not children of this task. Shared content plumbing (TASK-178) is also tracked separately because it serves multiple consumers.

WHY: some incidents affect the organization across many products: a critical vulnerability, leaked credentials, shared-platform outage, vendor breach, or privacy incident. Coordinators need one incident to engage product teams, collect triage and progress, and provide a safe consolidated view. Some of them hold many issues at once: a vulnerability disclosure program (VDP) or pentest report brings many findings across many products and repositories. That is still one incident, never one per vulnerability: findings are optional records inside it, and each team's work is action items that reference a finding and a repository (large-scale-incident-analysis.md §5.14).

WORK MODEL: action items are one incident record type in core/ with a kind, response or follow_up, shared with the postmortem (decisions/incident-management.md, amended 2026-11-04; the store is built by TASK-147.2). Coordination adds optional references on it (engagement, finding, repository, root incident id) rather than a task record of its own. D35–D38 (findings, per-repository progress, where items live, embargo and disclosure dates) are recorded in the coordination ADR by TASK-165.2.

SCOPE AND ORDER: after TASK-145 completes the incident rebuild in the doc-11 target shape, coordination is delivered first in whole epics. Engagement leads use the on-call capability when available; the coordinator can assign manually when no source is configured. The 2–3 week target means the Opsgenie end-of-support date is not a current sequencing constraint; TASK-146 removes Opsgenie as part of the GoAlert cutover.

TEAM COMPOSITION: Google Workspace is the primary IdP but does not yet have standardized team and role groups. Do not infer people from groups. Rosters contain person identities and manual additions; resolve the source for team/role membership when planning the first epic that needs it. If an external source is not ready, the epic must still close whole with person-level behavior and a separate follow-up.

PLAYBOOKS: provisioned organisation/team playbooks are delivered first; managed in-flight editing is a separate later epic. Both follow the organisation-content, provisioned-content, and managed-content decisions.

VALIDATION: a scripted staging CVE dry run and a scripted VDP walk-through (one report, several findings across several products and repositories, on paper against the MVP) are required at the post-MVP re-plan checkpoint; the walk-through confirms D35–D38 before E6 starts. A full tabletop exercise with product leads is optional because priorities outside this project may limit their availability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident-management and incident-coordination ADRs record the coordinated incident model and its incident, engagement, visibility, embargo, and severity boundaries; playbook and incident-type decisions are recorded in the A5 revision.
- [ ] #2 The delivery map orders coherent epics and dependencies; each epic is decomposed into reviewable single-PR implementation tasks when it is next, and is not considered delivered while temporary dual paths or fallbacks remain.
- [ ] #3 A CVE can be run end to end through Slack by hand, with API parity, before playbooks exist; the scripted dry run is completed, while a full product-lead tabletop remains optional.
- [ ] #4 Provisioned organisation/team playbooks, incident types, and per-type templates are delivered first; managed playbook edits follow through the shared validated, authorized, versioned, audited write path, with the configured Google template remaining the default.
- [ ] #5 A report with many findings (a VDP or pentest report) runs as one incident: findings are tracked inside it, each product's action items reference the finding and the repository, and the roll-up by finding shows progress across teams; a scripted VDP dry run is completed after the findings epic.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T00:44:00Z

---

2026-11-05 (TASK-145.6 OQ4, human): the report section writer matches the CDS postmortem template's Impact labels (end-users, cds staff, other government department(s), other) to drop empty groups and normalise heading styling (core/adapters/google_docs.py after TASK-145.6.1). These describe the template, not app wording: the label set belongs with the per-type document templates this epic manages; until then they stay adapter constants, and a template without them is left untouched.

---

created: 2026-11-05T15:54:00Z

---

2026-11-05 (human): TASK-145.11 turns the report section writer's template facts into a template profile that postmortem passes as data: groups dropped when empty, labels styled as body text, metadata labels, and guidance restored under named headings. Until then it is a postmortem constant. The per-type document templates this epic manages supply the profile per template; the configured Google template's profile stays the default.

---
<!-- COMMENTS:END -->
