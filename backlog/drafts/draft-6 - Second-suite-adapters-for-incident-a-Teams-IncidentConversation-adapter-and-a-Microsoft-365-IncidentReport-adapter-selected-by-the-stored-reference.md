---
id: DRAFT-6
title: >-
  Second-suite adapters for incident: a Teams IncidentConversation adapter and a
  Microsoft 365 IncidentReport adapter, selected by the stored reference
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - incident
  - later-wave
milestone: m-6
dependencies:
  - TASK-145.13
  - TASK-83
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
  - decisions/platform-transports.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2; m-6 Teams). decisions/incident-management.md: a second suite is one adapter per core interface and no subdomain change. This task adds a Teams adapter for IncidentConversation and a Microsoft 365 (Word in OneDrive or SharePoint) adapter for IncidentReport in features/incident/core/adapters/, using the Microsoft Graph vendor package (TASK-83.12). The stored reference selects the adapter; the new-incident policy setting may name the Microsoft tenant. Teams entrypoints for lifecycle, retrospective and scribe are thin handlers over the same services.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two adapters in core/adapters/ implement IncidentConversation and IncidentReport for Microsoft systems; the resolver selects by reference.system and tenant
- [ ] #2 No subdomain service changes to support the second suite beyond new entrypoints/teams.py handlers
- [ ] #3 An incident declared on Teams with a Microsoft report round-trips through show, status and timeline capture
<!-- AC:END -->
