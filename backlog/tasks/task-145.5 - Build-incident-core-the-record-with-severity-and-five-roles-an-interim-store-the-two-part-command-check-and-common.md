---
id: TASK-145.5
title: >-
  Build incident/core: the record with severity and five roles, an interim
  store, the two-part command check and common/
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:23'
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
- [ ] #3 find_incident_for_conversation resolves through IncidentStore and core/adapters/legacy_incidents.py is deleted
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 IncidentStore has an interim DynamoDB adapter reading the existing items (get, find by conversation, list, security flag) and an in-memory fake with the same cases; write operations are absent and listed for the slices that add them
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09); paths assume TASK-145.1 merged. Read path and types only: the write operations arrive with their first consumer (create in TASK-145.7, atomic field update in TASK-145.8, timeline append in TASK-145.9), which keeps this slice under the size gate and avoids speculative code. The description's bullets are read with that split.

## Discovered state
- core/domain.py (164 lines): TranscriptMessage, IncidentSecurityFlag, StatusUpdateStage, StatusUpdateState, StatusUpdateOrigin, StatusUpdateText, StatusUpdate. core/api.py (195): Protocols IncidentLookup (find_incident_for_conversation), IncidentSecurityReader (read flag), IncidentTranscriptReader, StatusUpdateStore; providers get_incident_lookup, get_incident_security_reader, get_incident_transcript_reader, get_status_update_store; find_incident_for_conversation. core/adapters/legacy_incidents.py (145): LegacyIncidentTableLookup scans the "incidents" table by channel_id (no index, paginator at 100-105), reads security_incident by Key id (85-94), over integrations.aws.client.get_aws_client with classify_aws_error; built by build_legacy_incident_lookup / build_legacy_incident_security_reader. core/adapters/status_updates.py (248) shows the adapter style to copy (client, _to_item/_from_item, classified failures, conditional put).
- Legacy item shape (app/models/incidents.py): id (uuid), channel_id, channel_name, name, user_id, teams, report_url, status ("Open"), created_at (epoch string), start_impact_time, end_impact_time, detection_time ("Unknown" or a value), environment, logs (list), meet_url, incident_commander, operations_lead, severity (str|None), retrospective_url, security_incident (bool|None). Written by modules/incident/db_operations.py (create_incident 53, update_incident_field 121 with list_append, log_activity 164, get_incident_by_channel_id 201, lookup_incident 216).
- Consumers of the lookup today: scribe status_update.py, status_update_approval.py and status_update_history.py take lookup=/security_reader= defaults from core.api; comms inherits them after TASK-145.4.

## Steps
1. common/: features/incident/common/__init__.py (empty), vocabulary.py (IncidentStatus StrEnum with the five values; Severity StrEnum SEV0..SEV3 with a docstring that 0 is an event spanning several products; IncidentRole StrEnum incident_commander, operations_lead, communications_lead, policy_lead, postmortem_owner; StatusUpdateStage moved here from core/domain.py with a re-export in core.api so no importer changes), settings.py (IncidentCoreSettings: legacy table name "incidents", new-incident tenant policy defaulting to the configured Google tenant; no I/O).
2. core/domain.py: frozen dataclasses ConversationReference(system, tenant, channel_id), ReportReference(system, tenant, document_id, link), VideoCallReference, PostmortemMeetingReference, ExternalCaseReference, SourceAlertReference (system, tenant, channel, message id); Incident(id, title, product, severity: Severity | None, security_flag: IncidentSecurityFlag, declarer, status: IncidentStatus, declared_at, detection_at | None, impact_start_at | None, impact_end_at | None, roles: Mapping[IncidentRole, str], conversation, report | None, video_call | None, postmortem_meeting | None, external_case | None, source_alert | None, environment); TimelineEntry(incident_id, posted_at, author, text, source_message) as its own record type. __post_init__ validates timezone-aware times as StatusUpdate does.
3. core/store.py: IncidentStore Protocol, read operations only: get(incident_id) -> OperationResult[Incident]; find_by_conversation(channel_id) -> OperationResult[str] (NOT_AN_INCIDENT / AMBIGUOUS_INCIDENT_CONVERSATION / classified failure, the legacy adapter's contract); list_active(window) -> OperationResult[Sequence[Incident]]; read_security_flag(incident_id). Write operations are added by the slices that need them, each with its own tests.
4. core/adapters/incidents.py: DynamoDbIncidentStore over get_aws_client, moving the scan and the flag read from legacy_incidents.py and adding _from_item: "Unknown" and blank times -> None, epoch strings -> aware datetimes, severity string -> Severity when it parses else None (logged), report_url -> ReportReference(system "google_docs", configured tenant, document id parsed with a local regex, link kept), meet_url -> VideoCallReference link-only, retrospective_url -> PostmortemMeetingReference link-only, channel_id -> ConversationReference(slack, configured tenant), incident_commander/operations_lead -> roles. Legacy ids stay the record ids. core/adapters/in_memory.py gains InMemoryIncidentStore (same file, same style as InMemoryStatusUpdateStore).
5. core/api.py: export the new types and IncidentStore; get_incident_store() provider (lru_cache, as the others); get_incident_lookup and get_incident_security_reader return the store (it satisfies both Protocols structurally, so scribe and comms call sites do not change); find_incident_for_conversation delegates to the store. Delete core/adapters/legacy_incidents.py and its two builders.
6. Tests under tests/unit/features/incident/core/: test_incident_core_record.py (invariants), test_incident_core_vocabulary.py (enums), test_incident_core_incident_store.py (Stubber-driven: get, find by conversation incl. ambiguous and missing, list, legacy item mapping edge values), test_incident_core_incident_store_fake.py, test_incident_core_api_surface.py extended (exports; lookup and security reader are the store); test_incident_core_incident_find.py and test_incident_core_incident_security_flag.py retargeted from the legacy adapter to the store.

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 (record with severity, five roles, timing fields; references with system and tenant) | 1, 2 | test_incident_core_record.py |
| 2 (vocabulary in common/, no I/O imports) | 1 | test_incident_core_vocabulary.py plus an import assertion (common imports nothing from adapters, store or providers) |
| 3 (interim adapter reads existing items; fake; read path) | 3, 4 | test_incident_core_incident_store.py, ..._fake.py; the timeline-record assertion moves to TASK-145.9 where append lands |
| 4 (find_incident_for_conversation through the store; legacy adapter deleted) | 5 | test_incident_core_incident_find.py; `rg legacy_incidents app` empty |
| 5 | all | gates |

## Test matrix
Store get: item present; missing (NOT_FOUND); unreadable item (classified); client error classified. find_by_conversation: blank id, none, one, several (ambiguous), scan pagination over two pages, ClientError. Mapping: "Unknown" times -> None; epoch string -> aware UTC datetime; severity "SEV1"/"1"/garbage; security_incident True/False/absent -> flag; report_url with and without a parsable document id; roles absent. Fake: parity with the Stubber cases. api: lookup and security reader are the same object as the store.

## Assumptions and doubts
- The legacy table name is fixed ("incidents", legacy_incidents.py:31) and the AWS settings carry the region/credentials; the terraform table has no channel_id index, so the scan stays until the store owns its layout (TASK-108/109).
- The severity values stored by the legacy declare modal need reading (incident.py severity picker options) to map them; confirm the 0-3 scale decision before merging (open question in the handoff).
- Moving StatusUpdateStage to common/ with a core.api re-export keeps comms imports stable; if the reviewer prefers it to stay in core/domain.py the step is dropped.

## Size
domain +130, vocabulary +45, settings +25, store +45, adapter +170, fake +60, api +25, deletion -145. About 350 production lines across 8 files. Under the gate; the writes are deferred for this reason.

## Blast radius and rollback
Read-only over the existing table; no new consumer except the existing lookup callers, which keep their contract. Single `git revert`.
<!-- SECTION:PLAN:END -->
