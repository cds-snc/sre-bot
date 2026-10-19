---
id: TASK-145.5.4
title: >-
  IncidentStore over RecordStore: end-state read operations, the incidents
  RecordTable, an in-memory fake, and full items from index reads in the records
  contract
status: Done
assignee: []
created_date: '2026-10-14 23:09'
updated_date: '2026-10-19 18:39'
labels:
  - incident
  - features
  - records
dependencies:
  - TASK-145.5.3
references:
  - decisions/incident-management.md
  - decisions/cloud-portability.md
  - app/contracts/records/store.py
  - 'https://github.com/cds-snc/sre-bot/issues/1693'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 390000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 5 of Stack K (handoff doc-13). The store exists but production does not use it yet. It reads end-state items only (those carrying record_version); the legacy item bridge is the next layer (the bridge subtask TASK-145.5.8), and TASK-145.5.5 wires both.

THIS SLICE
- core/store.py: the IncidentStore Protocol (one Protocol for the record, exported from core/api.py) and RecordIncidentStore over RecordStore. incidents_table(name) declares partition key id with the by_channel and open indexes. Table name comes from the incident core settings (TASK-145.5.3) where TASK-145.5.5 builds the store. RECORD_VERSION = 1 and OPEN_BUCKET = 'OPEN' are defined here for the writers.
- Read operations: get; find_by_conversation(conversation: ConversationReference) queries by_channel with a small bound, keeps only items whose conversation system and tenant match the caller's reference (two tenants can share one id), then applies zero (not an incident), one (the incident) or several (ambiguous); reaching the bound fails closed as ambiguous; index reads may be eventually consistent and are not unique; no bounded-list fallback; list_open (RecordQuery on open, partition OPEN, ordered by opened_at); read_security_flag, returning OperationResult[bool].
- End-state item parser (core/adapters/incident_items.py, pure): stored attributes are named after the record fields. Reads are tolerant: a reference with a system that is not a WorkplaceSystem member, an invalid shape or a blank tenant reads as no reference; a severity outside 0 to 4 or not an integer reads as None; an unreadable optional time reads as None; each is logged with the incident id and field. A required value that is unreadable (status, declared_by, declared_at, security_incident) makes the item a classified INCIDENT_RECORD_UNREADABLE result, never an exception. An item without record_version is also INCIDENT_RECORD_UNREADABLE until the bridge subtask TASK-145.5.8 lands.
- Domain edits (core/domain.py): Incident.declarer becomes declared_by (matches the stored name); security_flag: IncidentSecurityFlag is replaced by security_incident: bool, required, no third state. The IncidentSecurityFlag enum stays exported until TASK-145.5.5 moves comms to the bool and deletes it.
- core/adapters/in_memory.py: an in-memory IncidentStore fake for consumer tests, explicitly subclassing the Protocol.
- Records contract: the RecordStore docstring states that an index query returns full items, like a table query, and the conformance suite gains a case asserting a non-key attribute from an index query on both stores.
- Write operations are absent: create (TASK-145.7 sets open_bucket and opened_at), update (TASK-145.8 removes them on Closed), timeline append (TASK-145.9). timeline_table and the key-format helpers are not in this slice.

DECISION RECORD (human, 2026-10-14): key formats, applied by the writers. opened_at and timeline posted_at are fixed-width ISO-8601 UTC strings (isoformat(timespec=microseconds), +00:00), matching the repo's other stores; entry_key is '<posted_at>#<entry_id>', where entry_id is a uuid5 over system, tenant, conversation and message id for captured messages (a re-capture produces the same key) and a uuid4 for manual entries. The vendor message id stays in the entry's source_message reference. The opened_at format is applied by TASK-145.7 and TASK-145.8; timeline_table, entry_key and entry ids by TASK-145.9.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IncidentStore (Protocol in core/store.py, exported from core/api.py) is implemented over RecordStore with get, find_by_conversation, list_open and read_security_flag (returning bool), reading end-state items, tested against InMemoryRecordStore; no module in core/ imports an AWS client
- [x] #2 find_by_conversation takes the caller's ConversationReference, queries by_channel with a small bound, keeps only items matching its system and tenant, and handles zero, one, several (ambiguous), a blank id and the bound being reached (ambiguous, no bounded-list fallback); two tenants sharing one id are told apart; list_open returns only incidents carrying open_bucket, ordered by opened_at
- [x] #3 The end-state parser reads attributes named after the record fields (title, declared_by, declared_at, product, severity 0 to 4, security_incident, the five roles, one nested map per reference kind) with tolerant optional values: a severity outside 0 to 4, an unreadable optional time, a blank product or role, and a reference with a system that is not a WorkplaceSystem member, an invalid shape or a blank tenant read as not recorded, not assigned or no reference, each logged with the incident id and field, never raising
- [x] #4 An in-memory IncidentStore fake that explicitly subclasses the Protocol is importable from core/adapters/in_memory.py for consumer tests, with the same classifications as the real store
- [x] #5 The RecordStore docstring and conformance suite state and check that an index query returns full items on both stores
- [x] #6 No write operation is on IncidentStore, the store docstring names the slices that add them (TASK-145.7 create, TASK-145.8 update, TASK-145.9 timeline append), and timeline_table and the key-format helpers are absent from this layer
- [x] #7 A required value that is unreadable (status, declared_by, declared_at, security_incident) and an item without record_version return a classified INCIDENT_RECORD_UNREADABLE result logged with the incident id and field, never an exception; Incident carries declared_by and a required security_incident bool (IncidentSecurityFlag stays exported for TASK-145.5.5)
- [x] #8 The store takes no tenant ids and no settings object, and no module in features/incident imports a vendor settings slice (rg finds none); the legacy item bridge is not part of this layer
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Layer 5 of Stack K. Builds on TASK-145.5.3 (landed): Incident, the six reference types in core/domain.py; IncidentStatus, Severity in common/vocabulary.py; IncidentCoreSettings; WorkplaceSystem in contracts/workplace/. Reads of end-state items only; no write operation; no production wiring (TASK-145.5.5). The legacy item bridge (core/adapters/legacy_items.py and its hook in the store) is the bridge subtask TASK-145.5.8, the next layer; the store here has no legacy branch.

DECISIONS
1. Shape. core/store.py: IncidentStore Protocol (runtime_checkable), incidents_table(name), RECORD_VERSION = 1, OPEN_BUCKET = "OPEN", RecordIncidentStore(records: RecordStore, table: RecordTable). core/adapters/incident_items.py: pure end-state item parser. core/adapters/in_memory.py: InMemoryIncidentStore, explicitly subclassing IncidentStore (Protocol in core/store.py, no cycle; cloud-portability contract 4 end state). core/api.py exports IncidentStore only. OPEN_BUCKET stays here because list_open queries it; TASK-145.7 imports it. The opened_at format helper, timeline_table, entry_key and entry ids are not here (TASK-145.7 and TASK-145.9 apply the 2026-10-14 key-format record in the description).
2. Stored attributes (end state, named after the record fields): id, record_version (int, 1), title, status (exact IncidentStatus value), declared_by, declared_at, product, severity (int 0 to 4), security_incident (bool), detected_at, impact_started_at, impact_ended_at (times are fixed-width ISO-8601 UTC strings with +00:00), incident_commander, operations_lead, communications_lead, policy_lead, postmortem_owner (person ids; absent = not assigned), channel_id (top level: the deployed by_channel index key and the lookup copy of conversation.vendor_id), open_bucket and opened_at (as decided), and one nested map per reference kind: conversation, report, video_call, postmortem_meeting, external_case, source_alert. A reference map is {system, tenant, vendor_id, url} with url an optional hint the owning adapter can re-render; a map is replaced whole, never patched. source_alert is read as a ResourceReference map until TASK-145.7 decides its shape (SourceAlertReference already fits).
3. Domain edits (this layer owns domain.py): Incident.declarer is renamed declared_by; security_flag is removed and security_incident: bool is a required field placed after declared_at (no default, no third state; validated as bool). IncidentSecurityFlag, IncidentSecurityReader and comms are untouched; TASK-145.5.5 moves comms to the bool and deletes the enum. IncidentStatus stays strict and required.
4. Protocol (every method returns OperationResult; a store failure is a classified result with a generic message and the store's status, error_code and retry_after, never an exception, never provider text):
   - get(incident_id) -> Incident; blank id or no item: NOT_FOUND NOT_AN_INCIDENT.
   - find_by_conversation(conversation: ConversationReference) -> Incident. Blank vendor_id: NOT_FOUND NOT_AN_INCIDENT with no query. RecordQuery(partition=conversation.vendor_id, index="by_channel", limit=_CONVERSATION_QUERY_BOUND = 10). Items whose conversation map is unreadable, or whose system or tenant differ from the caller's, are skipped before parsing and never make the call fail. Matches: zero -> NOT_FOUND NOT_AN_INCIDENT; one -> parsed Incident; several, or the bound reached -> PERMANENT_ERROR AMBIGUOUS_INCIDENT_CONVERSATION (fail closed). Projection is ALL (TASK-145.5.1), so no second get.
   - list_open() -> Sequence[Incident]; RecordQuery(partition=OPEN_BUCKET, index="open"), ascending by opened_at.
   - read_security_flag(incident_id) -> bool.
   - The docstring names the slices that add writes (TASK-145.7 create, TASK-145.8 update, TASK-145.9 timeline append).
5. Classification of an item without record_version (until the bridge subtask TASK-145.5.8 lands): PERMANENT_ERROR with ErrorCode.INCIDENT_RECORD_UNREADABLE (new code), generic message, logged event incident_item_not_upgraded with incident id. It applies to get, read_security_flag, list_open (an item in the open index) and a find_by_conversation candidate (without the version its tenant cannot be checked, so it cannot be skipped; fail closed). No production path reads the store before the bridge, so this has no runtime effect.
6. Parser rules. Required, else INCIDENT_RECORD_UNREADABLE logged with incident id, field and (for status only) the stored value: id, title and declared_by non-blank strings; status exactly an IncidentStatus value; declared_at an aware ISO-8601 string; security_incident a bool. Tolerant, else None with event incident_field_unreadable (incident id, field, stored value; never a whole item, never a token): optional times (a naive or unparseable string), severity (int or integral Decimal 0 to 4), product (blank = not recorded), the five roles (blank = not assigned), every reference (system not a WorkplaceSystem member, invalid shape, blank tenant or vendor_id).
7. Tenant ids: the end-state reference map carries its own tenant, so this store takes none; the bridge subtask TASK-145.5.8 adds the construction argument (tenant ids from the configured-systems read, TASK-145.5.5; never a vendor settings slice).
8. Fake: InMemoryIncidentStore.seed(incident, *, open=None) (open defaults to the status being open); find_by_conversation matches system, tenant and vendor_id and returns the same classifications; list_open orders by declared_at as a stand-in for opened_at, documented. Seeded incidents are always readable.
9. Records contract: RecordStore docstring in contracts/records/store.py states that an index query returns full items like a table query (indexes are declared with full projection); the query docstring in infrastructure/records/service.py mirrors it; TestIndexQueries gains a case asserting a non-key attribute (value) on both stores (the moto index already projects ALL, conftest.py).
10. Logging: structlog; events carry operation, incident_id, field; store failures log table, status, error_code only.
11. Terminology: new names and docs say not recorded, not assigned, not rated or unreadable; none of them says unknown.
12. Deprecated or buggy constructs in touched files: none found.

STEPS (tests first in each)
1. contracts/records/store.py and infrastructure/records/service.py docstrings; conformance case. [AC5]
2. contracts/operations/codes.py INCIDENT_RECORD_UNREADABLE; core/domain.py declared_by and security_incident; record tests in place. [AC7]
3. core/store.py: Protocol, incidents_table, constants. [AC1, AC6]
4. core/adapters/incident_items.py parser. [AC3, AC7]
5. core/store.py RecordIncidentStore reads. [AC1, AC2]
6. core/adapters/in_memory.py fake. [AC4]
7. core/api.py export; features/incident/README.md core row (IncidentStore and its fake exist, unused until TASK-145.5.5; Incident carries declared_by and security_incident; the bridge follows). [AC6]

CALL SITES
- app/contracts/records/store.py RecordStore docstring; app/infrastructure/records/service.py:383 query docstring.
- app/tests/integration/infrastructure/records/test_records_store_query_conformance.py:156 TestIndexQueries; conftest.py RECORDS_TEST_TABLE and by_user index.
- app/contracts/operations/codes.py:78 (before INVALID_*); tests/unit/contracts/operations/test_error_code_registry.py if it enumerates.
- app/features/incident/core/domain.py:230,257 (declarer), :234,261 (security_flag) and Incident.__post_init__; core/api.py __all__ and imports; core/adapters/in_memory.py.
- In-place tests: tests/unit/features/incident/core/test_incident_core_incident_record.py (lines 28 declarer, 41 and 67 security_flag), test_incident_core_api_surface.py (__all__ gains IncidentStore; IncidentSecurityFlag stays).
- terraform/dynamodb.tf:91-150 index names the table declaration must match; not edited.
- Not touched: comms/service.py:106,178,257,361,498 and core/adapters/legacy_incidents.py (TASK-145.5.5); the bridge.

TEST MATRIX (new files in app/tests/unit/features/incident/core/, unit marker, top-level imports)
- test_incident_core_incident_store_get.py: found over InMemoryRecordStore; missing and blank id; store error classified with generic message; item without record_version -> unreadable; unreadable status -> unreadable with stored value logged.
- test_incident_core_incident_store_find_by_conversation.py: zero, one (non-key attributes present), several, blank id, two tenants sharing one id (only the matching tenant found; both present with the same tenant -> ambiguous), other-tenant item unreadable elsewhere does not fail the call, bound reached -> ambiguous, candidate without record_version -> unreadable, store error with retry_after. Zero/one/several/blank also run parametrized against the fake.
- test_incident_core_incident_store_list_open.py: only items carrying open_bucket, ordered by opened_at, empty, store error, item without record_version.
- test_incident_core_incident_store_security_flag.py: true, false, non-bool -> unreadable, missing incident, blank id, error.
- test_incident_core_incident_item_required.py: each required field missing or invalid -> unreadable.
- test_incident_core_incident_item_tolerant.py: severity 0 to 4 as int and Decimal, out of range, non-integer, absent; times aware/naive/garbage; product and roles blank; log events carry incident id and field (structlog.testing.capture_logs).
- test_incident_core_incident_item_references.py: each kind, url optional, system not a member -> no reference and incident intact, invalid shape, blank tenant, source_alert read as a ResourceReference map.
- test_incident_core_incident_store_fake.py: explicit subclass and isinstance, classifications as the real store, open flag and order.
- test_incident_core_incident_store_table.py: incidents_table key and index names match terraform.
Boundary: query bound; Decimal numbers. Failure: store errors, unreadable items. No authorization or idempotency (reads).

AC TRACEABILITY: AC1 steps 3, 5 (get, find, list_open, security tests; rg and lint-imports show no AWS import in core/store.py or the parser); AC2 step 5; AC3 step 4 (tolerant and references files); AC4 step 6; AC5 step 1; AC6 steps 3, 7 (api_surface, fake test); AC7 steps 2, 4, 5 (required, tolerant, store_get tests); AC8 step 5 (two-tenant test). Every step maps to an AC.

SIZE AND GATE
8 production files (contracts/records/store.py, infrastructure/records/service.py, contracts/operations/codes.py, core/domain.py, core/store.py, core/adapters/incident_items.py, core/adapters/in_memory.py, core/api.py) plus the README. About 390 production lines including docstrings (store.py ~175, parser ~130, fake ~60, domain ~15, rest ~10); under 300 executable. One subsystem. Passes, near the line; no mechanical refactor is mixed in (the declarer rename has no consumer).

ASSUMPTIONS AND DOUBTS (verify)
- by_channel and open are ACTIVE with projection ALL before the cutover (TASK-145.5.1 tf_apply); checked in TASK-145.5.5.
- DynamoDB numbers deserialize to Decimal (parser accepts Decimal; tested).
- Writers (TASK-145.7, TASK-145.8) adopt decision 2 and write record_version = RECORD_VERSION on every create; the bridge and the TASK-145.5.7 upgrade job add it to existing items.
- The bound 10 is far above any real duplicate-id count; reaching it is treated as ambiguous.

BLAST RADIUS AND ROLLBACK
No production caller reads the store, so runtime behaviour is unchanged; Incident (declared_by, security_incident) has no consumer. One git revert restores everything. No terraform, no environment variable, no ordering constraint.

GATES (from app/): ruff check ., ruff format --check, lint-imports, mypy on touched files (0 in touched), pytest tests --ignore=tests/smoke.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented end-state reads (layer 5 of Stack K).

- core/store.py: IncidentStore Protocol (exported from core/api.py; get, find_by_conversation, list_open, read_security_flag, no write operation, docstring names TASK-145.7/145.8/145.9), incidents_table(name) with by_channel and open matching terraform/dynamodb.tf (test reads the tf text), RECORD_VERSION = 1, OPEN_BUCKET = 'OPEN', RecordIncidentStore over RecordStore. find_by_conversation: by_channel with bound 10; a full page is AMBIGUOUS_INCIDENT_CONVERSATION; candidates of another system or tenant, or with an unreadable conversation map, are skipped before parsing; a candidate without record_version fails closed as INCIDENT_RECORD_UNREADABLE. list_open fails whole on one unreadable item (a partial list would hide an open incident). Store failures keep status, error_code and retry_after with a generic message; NOT_FOUND from a query becomes PERMANENT_ERROR.
- core/adapters/incident_items.py: pure parser; required id, title, status (exact value), declared_by, declared_at (aware), security_incident (bool) else INCIDENT_RECORD_UNREADABLE (status logs its stored value); tolerant optional times, severity (int or integral Decimal 0-4, bools refused), product, roles, references (logged incident_field_unreadable with incident id and field; reference maps are never logged since url may be a vendor link). read_reference is generic over the reference kind.
- core/adapters/in_memory.py: InMemoryIncidentStore(IncidentStore), seed(incident, *, open=None), same classifications (shared helpers in store.py), list_open by declared_at.
- core/domain.py: Incident.declared_by; security_incident: bool required after declared_at, validated as bool. IncidentSecurityFlag untouched (TASK-145.5.5).
- contracts: ErrorCode.INCIDENT_RECORD_UNREADABLE; RecordStore and DynamoDBRecordStore.query docstrings state index queries return full items; conformance case on both stores.
- features/incident/README.md core row updated.

Size: about 514 production lines with docstrings (store.py 228, parser 206, fake +57, rest ~23), about 345 executable; above the plan's ~390/under-300 estimate. The parser grew with explicit keyword arguments that mypy can check.

AC1 and AC8 scope: the new modules import no AWS client and no settings. core/adapters/legacy_incidents.py and status_updates.py still import integrations.aws (client and settings); they predate this layer and go with TASK-145.5.5 and TASK-145.5.6. No module in features/incident imports a Slack or Google settings slice.

Gates (from app/): ruff check . -> All checks passed; ruff format --check . -> 961 files already formatted; lint-imports -> 12 kept, 0 broken; bin.check_fake_coverage -> OK; mypy . -> 48 errors in 19 files, 0 in touched files; pytest tests --ignore=tests/smoke -> 5174 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-15 18:27
---
Plan approved (human, 2026-10-15): end-state reads only; the legacy item bridge is TASK-145.5.8.
---
<!-- COMMENTS:END -->
