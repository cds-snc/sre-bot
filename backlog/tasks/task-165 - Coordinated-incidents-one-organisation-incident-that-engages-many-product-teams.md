---
id: TASK-165
title: >-
  Coordinated incidents: one organisation incident that engages many product
  teams
status: To Do
assignee: []
created_date: '2026-10-23T18:47:00Z'
updated_date: '2026-10-28T19:42:00Z'
labels:
  - incident
milestone: m-7
dependencies:
  - TASK-167
type: feature
ordinal: 437000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
PROBLEM
Some incidents belong to the organisation, not to one product: a critical CVE or supply-chain compromise, leaked credentials, a shared-platform outage, a vendor breach, a privacy breach. A coordinator engages many product teams; each answers whether it is affected and does its own share; the coordinator and senior management need one consolidated picture. Commercial tools cover parts of this, fail Canadian residency or French, or need licences that do not reach every participant.

DECISIONS
- One kind of incident, built from parts: the incident record; working-surface bindings (Slack, Teams or the Backstage incident page; at least one while active, Backstage alone is acceptable); facets attached when needed (report, video call, comms, postmortem, coordination); engagements; typed links between incidents (parent, related, duplicate). No separate large-incident type, and nothing depends on knowing the incident type.
- An engagement is an edge from the coordinating incident to a product or team holding its triage answer, lead, deadline and flags; it may be fulfilled by a child incident. Users call it a workstream. Weight is chosen per engagement at any time: not affected is one small record, an affected product can grow into a child incident and shrink back.
- Roles: the coordinator is SRE or Security on-call with a deputy; each product lead is that product's on-call, auto-assigned and reassignable. The coordinator adds or removes products at any time.
- Triage is explicit per product, with a deadline and escalation of silence. Progress status is required; tasks are the generic breakdown; synced repository items come later as an adapter.
- Relationships: promote, attach and detach, link, merge.
- Severity is the handbook scale, chosen by a person, mutable, never computed from breadth.
- Confidentiality: embargo mode from declaration, lifted by the coordinator.
- Reporting: a coordinator roll-up; a senior-management summary as its own feature like the status update; sitrep reminders; metrics; per-product external updates. One organisation-level postmortem; workstream findings are its inputs.
- Playbooks are opt-in shortcuts at two levels, organisation and team: suggested, previewed, applied by a person, additive and one-shot, never automatic; layered defaults < organisation < team < person. They may personalise features within bounds each feature sets, starting with status-update fields and AI drafting guidance. Team playbooks live in a central configuration repository, a folder per team owned through CODEOWNERS, read through a catalogue port; organisation-specific content stays out of the bot's code.
- On-call and paging through self-hosted GoAlert, replacing Opsgenie, with SMS through GC Notify; the bot reads who is on call and raises pages through it, never pages itself.
- Cloud investigations: the coordinator can hand a confirmed, unclassified brief to AWS DevOps Agent (Azure SRE Agent once its API is GA) where an agent already covers the account; agents stay read-only, the bot relays their milestones and findings to every bound surface, and findings are inputs, never published as-is.
- The HTTP API resource model comes first; Slack ships first; Teams and the Backstage plugin use the same services. Declare is built once in this shape in the incident rebuild; coordination follows as this epic, in single-PR slices.
- Pilot with SRE as the usual coordinator, after tabletop exercises with a few product leads. Working label: coordinated incident / incident coordonné.

This coordinator is broken out into subtasks as the incident-management ADR is amended.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The incident-management ADR records the coordinated-incident model and the decisions above
- [ ] #2 Subtasks cover engagement and triage, workstreams and links, embargo, roll-up and the senior-management summary, playbooks and feature personalisation, GoAlert on-call and paging, and cloud investigations, each a single PR
- [ ] #3 A CVE can be run end to end in Slack by hand, with API parity, before playbooks exist
- [ ] #4 Team playbooks, incident types and per-type document templates are managed content with a provisioned starting set (decisions/organisation-content.md, managed-content.md, provisioned-content.md): read through ports the incident feature owns, written through one validated, authorised, versioned and audited path; the template a type uses is managed and the configured Google template id is the default
<!-- AC:END -->
