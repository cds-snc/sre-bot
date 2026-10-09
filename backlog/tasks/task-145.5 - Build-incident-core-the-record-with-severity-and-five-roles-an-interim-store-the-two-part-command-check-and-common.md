---
id: TASK-145.5
title: >-
  Build incident/core: the record with severity and five roles, an interim
  store, the two-part command check and common/
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.1
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 355000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer B1 of TASK-145. Builds the record and its store in features/incident/core with no new consumer yet; the legacy module keeps working on the same table.

THIS SLICE
- core/domain.py: Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles as person references: incident commander, operations lead, communications lead, policy lead, postmortem owner), the typed references (conversation, report, video call, postmortem meeting, external case, source alert) each carrying system, tenant and vendor id plus the vendor link, TimelineEntry as its own record. Frozen dataclasses. The existing IncidentSecurityFlag stays and becomes a field of the record.
- common/vocabulary.py: IncidentStatus (Open, In Progress, Ready to be Reviewed, Reviewed, Closed), Severity (levels 0 to 3; confirm the scale before merging), the role names, StatusUpdateStage moved from core/domain.py, and the action ids one subdomain renders and another handles. common/settings.py: the incident settings tree (response, comms, postmortem slices; the new-incident system policy setting defaulting to the only configured tenant). No I/O in common/.
- core/store.py: IncidentStore (create, get, find by conversation reference, update one field atomically, list for a window, append a timeline entry as its own record) and an interim adapter in core/adapters/ over the existing DynamoDB incidents table that reads today's items and maps bare ids to references for the configured tenant; an in-memory fake. No read-modify-write and no list-append. TASK-108 and TASK-109 later swap the inside.
- core/api.py: the domain types, IncidentStore, its provider, find_incident_for_conversation and the security flag read served by the store, and conversation_is_writable. core/adapters/legacy_incidents.py and the separate IncidentLookup and IncidentSecurityReader Protocols are deleted once the store answers both.
- No legacy module change; the legacy_surface suite is unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 core/domain.py defines Incident with severity, the five roles and the four timing fields, and every reference type carries system and tenant
- [ ] #2 common/vocabulary.py defines IncidentStatus, Severity and the role names; common/ imports no adapter, store or provider module
- [ ] #3 IncidentStore has an interim DynamoDB adapter reading the existing items and an in-memory fake; a store test proves timeline entries are separate records with no list-append
- [ ] #4 find_incident_for_conversation resolves through IncidentStore and core/adapters/legacy_incidents.py is deleted
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
