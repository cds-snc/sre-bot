---
id: TASK-165
title: >-
  Coordinated incidents: one organisation incident that engages many product
  teams
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
updated_date: '2026-11-03T19:02:00Z'
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

WHY: some incidents affect the organization across many products: a critical vulnerability, leaked credentials, shared-platform outage, vendor breach, or privacy incident. Coordinators need one incident to engage product teams, collect triage and progress, and provide a safe consolidated view.

SCOPE AND ORDER: after TASK-145 completes the incident rebuild in the doc-11 target shape, coordination is delivered first in whole epics. Engagement leads use the on-call capability when available; the coordinator can assign manually when no source is configured. The 2–3 week target means the Opsgenie end-of-support date is not a current sequencing constraint; TASK-146 removes Opsgenie as part of the GoAlert cutover.

TEAM COMPOSITION: Google Workspace is the primary IdP but does not yet have standardized team and role groups. Do not infer people from groups. Rosters contain person identities and manual additions; resolve the source for team/role membership when planning the first epic that needs it. If an external source is not ready, the epic must still close whole with person-level behavior and a separate follow-up.

PLAYBOOKS: provisioned organisation/team playbooks are delivered first; managed in-flight editing is a separate later epic. Both follow the organisation-content, provisioned-content, and managed-content decisions.

VALIDATION: a scripted staging CVE dry run is required at the post-MVP re-plan checkpoint. A full tabletop exercise with product leads is optional because priorities outside this project may limit their availability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident-management and incident-coordination ADRs record the coordinated incident model and its incident, engagement, visibility, embargo, and severity boundaries; playbook and incident-type decisions are recorded in the A5 revision.
- [ ] #2 The delivery map orders coherent epics and dependencies; each epic is decomposed into reviewable single-PR implementation tasks when it is next, and is not considered delivered while temporary dual paths or fallbacks remain.
- [ ] #3 A CVE can be run end to end through Slack by hand, with API parity, before playbooks exist; the scripted dry run is completed, while a full product-lead tabletop remains optional.
- [ ] #4 Provisioned organisation/team playbooks, incident types, and per-type templates are delivered first; managed playbook edits follow through the shared validated, authorized, versioned, audited write path, with the configured Google template remaining the default.
<!-- AC:END -->
