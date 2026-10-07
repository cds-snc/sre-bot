---
id: TASK-38.1
title: >-
  Build features/incident/core: the incident record, its store over the storage
  contract, the in-memory fake and the two-part command check
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-07 14:20'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-124.5
  - TASK-27.2
  - TASK-108
  - TASK-109
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/workplace-systems.md
parent_task_id: TASK-38
priority: medium
ordinal: 306000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-38 (expand). decisions/incident-management.md: the system of record is the incident record in app storage, keyed by an app-generated id; the conversation is a resource of the incident, never its key.

THIS SLICE builds features/incident/core/ and features/incident/common/ with no consumer yet:
- core/domain.py: Incident (title, product, severity, security flag, declarer, status, declared/detection/impact-start/impact-end, incident commander, operations lead), IncidentStatus (Open, In Progress, Ready to be Reviewed, Reviewed, Closed), TimelineEntry, and the reference types, each a frozen dataclass carrying system, tenant and vendor id plus the vendor-provided link where one exists: ConversationReference, ReportReference, VideoCallReference, RetrospectiveReference, ExternalCaseReference, SourceAlertReference. Person references are an email or platform account today and switch to a person id with TASK-83.
- core/store.py: the IncidentStore interface (create, get, find by conversation reference, update one field atomically, list for a window, append a timeline entry as its own record) and its implementation over the storage contract resolved from the service registry; no DynamoDB type, key or expression crosses out of it. The plan decides the storage layout; it must read the existing incidents items so legacy and rebuilt surfaces share one record during the cutover series, and it maps bare legacy ids to references with the single configured tenant.
- an in-memory fake of IncidentStore in the package (cloud-portability.md fake contract).
- core/api.py: the public surface: the domain types, IncidentStore, the provider, find_incident_for_conversation (every command: a known incident or a classified refusal) and conversation_is_writable (only before a write to the conversation).
- common/settings.py: the incident settings tree (lifecycle, retrospective, scribe slices; the new-incident system policy setting defaulting to the only configured tenant); common/vocabulary for shared action ids. No I/O.

No read-modify-write and no vendor list-append: timeline entries are records under the incident. No legacy module changes; the legacy_surface suite is unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/core/api.py exposes the incident domain types, the reference types with system and tenant fields, IncidentStore, its provider, find_incident_for_conversation and conversation_is_writable; nothing else in core/ is imported from outside it
- [ ] #2 IncidentStore is implemented over the storage contract from the service registry and by an in-memory fake; the same test suite runs against both; no DynamoDB type, key or expression appears outside the implementation
- [ ] #3 Timeline entries are written as their own records; no list_append and no get-then-put in core/store.py (review and test)
- [ ] #4 A status update on an incident whose conversation is archived succeeds through the store; conversation_is_writable is not called by the store
- [ ] #5 features/incident/common/ has no I/O and holds the settings tree and shared vocabulary only; the umbrella layers contract lists core above common with exhaustive = true
- [ ] #6 No existing production module changes other than app/pyproject.toml; the legacy_surface suite is green with no file change; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06: TASK-140.3 adds core's find_incident_for_conversation with an interim adapter over the legacy incidents table, and TASK-140.4 adds StatusUpdate records under the incident id (table sre_bot_incident_status_updates). This task's store replaces the interim lookup adapter behind the same interface; the status-update records keep their keys.

2026-10-07 (TASK-140.3 planning): TASK-140.3 adds a standalone lookup Protocol in core/api.py whose one method is find_incident_for_conversation (conversation id -> OperationResult with the legacy UUID, or a classified not-an-incident refusal), served by an interim direct DynamoDB adapter in core/adapters/ that scans the legacy incidents table. This task must serve that Protocol from the store without a scan, and its plan chooses how (for example an index record per conversation, or another key-addressable read); the interim adapter is deleted here.

2026-10-07 (TASK-140.4): core/api.py now has StatusUpdateStore served by core/adapters/status_updates.py, an interim adapter directly over integrations.aws (table sre_bot_incident_status_updates, PK INCIDENT#<uuid>, SK UPDATE#<seq:06d>), plus core/adapters/in_memory.py. When this task puts core on the storage contract (after TASK-108/109), move that adapter onto it too: same Protocol and keys, conditional put with ALL_OLD replay detection must stay expressible through the contract.
<!-- SECTION:NOTES:END -->
