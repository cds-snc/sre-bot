---
id: TASK-97
title: >-
  Decide the incident management architecture: system of record, coordination
  boundary, and whether to back it with an external IR platform (DFIR-IRIS)
status: To Do
assignee: []
created_date: '2026-09-16 14:24'
updated_date: '2026-09-16 14:38'
labels:
  - architecture
  - incident
  - phase-5
milestone: m-5
dependencies:
  - TASK-38
references:
  - decisions/workplace-systems.md
  - decisions/feature-packages.md
  - decisions/outbound-clients.md
  - decisions/layers.md
  - app/modules/incident
priority: high
ordinal: 222000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ARCHITECTURE DECISION, no implementation. Produces a decisions/ record and an implementation-ready packet; TASK-38 (relocation) proceeds independently and must not prejudge this.

CONTEXT. modules/incident is the largest legacy surface (4636 LOC, 17 modules). It was designed around Google Workspace and DynamoDB: the incident list lives in a Google Sheet, the report lives in a Google Doc, the retro is a Google Calendar event with a Meet link, and the record in DynamoDB is reached through hand-built AttributeValue dicts. Human direction 2026-09-16: incident is to be redesigned from the ground up, with no assumption that any existing logic survives. A report document may or may not exist. A list of incidents and their statuses almost certainly exists, tracked as app-level database records and definitely not a spreadsheet. A video call probably exists, and which tool provides it is unknown and not yet interesting.

THE QUESTION THIS TASK ANSWERS. What does the SRE bot own, and what does it coordinate?
- Option A - the bot owns incident management. Incident records, statuses, timeline and artifacts are app records in the storage capability, and the bot is the system of record.
- Option B - the bot coordinates, an external IR platform owns the case. DFIR-IRIS (open-source DFIR case management, REST API) was raised as a candidate: a richer and more mature system, feature-complete for case management, timeline, evidence and reporting. The bot would keep what only it can do - conversation lifecycle in Slack or Teams, launching a video call, paging, nudging, notifications, workplace artifacts - and delegate the case itself to the platform API.
- Option C - a split: the bot owns a thin coordination record (which channel, which platform case, which artifacts) and the platform owns the case content.

WHY IT IS WORTH DECIDING EARLY, EVEN THOUGH IMPLEMENTATION COMES LATER. The answer determines whether an app-owned incident domain model, its storage schema and its migration off Google Sheets are worth building at all. Under Option B or C much of that investment is wasted or reduced to a reference record. The decision is cheap; the work it governs is not.

INPUTS TO GATHER
- DFIR-IRIS API surface, auth model, self-hosting and operational cost, licence, data residency, and whether it can be reached from the app deployment. Use web research; do not rely on recall.
- What the current feature actually does that users depend on, separated from how it does it (command surface, notifications, the retro flow, the status lifecycle, metrics reporting).
- Who consumes the incident metrics sheet today and what would replace it.
- The related open defects, which are evidence of the current design rather than work to schedule here: TASK-73 (status updates never reach the sheet), TASK-86 (retro events drop description, reminders and conference requestId), TASK-81 (folder display limit shim), TASK-87 (non-idempotent Workspace writes).

CONSTRAINTS ON WHATEVER IS CHOSEN (these are design inputs, not build steps; they were moved here from TASK-38 on 2026-09-16 because they describe the redesigned feature and not the relocation)
- No record of truth in a workplace document or spreadsheet. Anything the app keeps lives in app storage through the storage capability; a surviving document or sheet is a collaboration space the app references, or a write-only projection never read back into a business decision (decisions/workplace-systems.md rule 5).
- No new app/infrastructure/<service>/ Protocol for a workplace concern (rule 1). Where a workplace system is used, one adapter per system sits behind a feature-owned port, and which system applies is data - the artifact's stored reference, the conversation's platform, the person's linked account - never a global provider setting (rule 3).
- Every stored workplace-artifact reference carries its system and tenant alongside the vendor id; no bare vendor ids, and no human link built by string-formatting a vendor URL (rule 4). modules/incident/core.py:176, :182 and :481 hardcode a docs.google.com URL today.
- Hosting services (storage, queue, idempotency, secrets) are reached only through capability Protocols, so moving the app off AWS to Azure, GCP or on-prem touches no incident code.
- No persisted state is written with a read-modify-write or a vendor list-append.
- An external IR platform, if chosen, is an outbound integration governed by decisions/outbound-clients.md and sdk-typing.md, behind a feature-owned adapter returning OperationResult - never a new infrastructure capability.

DEPENDENCIES AND COUPLINGS
- The storage operations incident would need are TASK-27.1 and TASK-27.2.
- Person and linked-account resolution is TASK-83.
- While incident persistence stays on the provisional packages/aws_platform DynamoDB adapter, the seam baseline TASK-25.2.5.5 creates cannot empty, so TASK-88 cannot dissolve packages/aws_platform. Whichever option is chosen must say when incident leaves that adapter.
- TASK-80 asks whether Google Docs should be promoted to an infrastructure DocumentProvider. decisions/workplace-systems.md rule 1 now answers that with no; TASK-80 needs re-scoping or closing, and this task should state the replacement expectation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decisions/ record is added or amended stating which of the options is chosen, what the SRE bot owns, what it coordinates, and where the system of record lives
- [ ] #2 If an external IR platform is chosen, the evaluation is recorded with sourced evidence gathered from current documentation (API surface, auth, hosting, licence, data residency, operational cost) rather than recall, and the integration is scoped as a feature-owned adapter under decisions/outbound-clients.md, never an infrastructure capability
- [ ] #3 The constraints listed in the description are carried into the chosen design and each one is either satisfied or recorded as a named, time-boxed divergence
- [ ] #4 The user-visible capabilities of today's feature are inventoried separately from their current implementation, so the redesign can drop implementations without silently dropping capabilities
- [ ] #5 An implementation-ready packet exists with right-sized backlog tasks under the single-PR size gate, sequenced against TASK-27.1, TASK-27.2, TASK-83 and TASK-38, and stating when incident leaves the provisional packages/aws_platform DynamoDB adapter so TASK-88 can dissolve that package
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 14:37
---
2026-09-16 (human decision on sequencing): TASK-38 now runs AHEAD of this decision, not the other way round. The de-vendorized core it produces (AC#13: the incident, its status lifecycle, its participants and its artifact references as vendor-agnostic frozen dataclasses) is worth finishing on its own merits and is a direct input here - comparing an app-owned design against an external IR platform is concrete once those concepts exist as types, and speculative before. Hence the dependency on TASK-38.

What can still start immediately, in parallel with TASK-38: the DFIR-IRIS evaluation (API surface, auth, hosting, licence, data residency, operational cost, reachability from the deployment), and the inventory of user-visible capabilities separated from their current implementation. Those are research, not design, and neither waits.

What must NOT start before this decision lands: any new persistence design for incident - a storage schema, a migration off the incident sheet, a richer app-owned domain beyond what TASK-38 needs to de-vendorize what already exists. If an external platform ends up owning the case, that work shrinks to a thin coordination record.
---
<!-- COMMENTS:END -->
