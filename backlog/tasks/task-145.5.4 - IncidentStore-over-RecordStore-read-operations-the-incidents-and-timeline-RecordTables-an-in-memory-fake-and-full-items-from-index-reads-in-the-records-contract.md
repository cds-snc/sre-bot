---
id: TASK-145.5.4
title: >-
  IncidentStore over RecordStore: read operations, the incidents and timeline
  RecordTables, an in-memory fake, and full items from index reads in the
  records contract
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
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
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 390000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 5 of Stack K (handoff doc-13). The store exists but production does not use it yet.

THIS SLICE
- core/store.py: the IncidentStore Protocol (one Protocol for the record, exported from core/api.py) and its implementation over RecordStore. incidents_table(name) declares partition key id with the by_channel and open indexes; timeline_table(name) declares (incident_id, entry_key). Table names come from the incident core settings (TASK-145.5.3).
- Read operations: get, find_by_conversation (RecordQuery on by_channel; zero results is not an incident, one is the incident, several is ambiguous; index reads may be eventually consistent and are not unique; no bounded-list fallback), list_open (RecordQuery on open, partition OPEN, ordered by opened_at), read_security_flag.
- Mapping legacy items: Unknown or blank times become None and epoch strings become aware UTC; sev-1..sev-4 become SEV1..SEV4, none and blank become None, other values None and logged with the incident id and field; teams[0] is the product; bare ids become references with the platform tenant ids (TASK-145.5.3).
- Key formats (human, 2026-10-14): opened_at and timeline posted_at are fixed-width ISO-8601 UTC strings (isoformat(timespec=microseconds), +00:00), matching the repo's other stores; entry_key is '<posted_at>#<entry_id>', where entry_id is a uuid5 over system, tenant, conversation and message id for captured messages (a re-capture produces the same key) and a uuid4 for manual entries. The vendor message id stays in the entry's source_message reference.
- core/adapters/in_memory.py: an in-memory IncidentStore fake for consumer tests (structural, like InMemoryStatusUpdateStore; feature Protocols need no explicit subclass).
- Records contract: the RecordStore docstring states that an index query returns full items, like a table query, and the conformance suite gains a case asserting a non-key attribute from an index query on both stores.
- Write operations are absent: create (TASK-145.7 sets open_bucket and opened_at), update (TASK-145.8 removes them on Closed), timeline append (TASK-145.9).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentStore is implemented over RecordStore with get, find_by_conversation, list_open and read_security_flag, tested against InMemoryRecordStore; no module in core/ imports an AWS client
- [ ] #2 find_by_conversation handles zero, one and several index results and a blank id, and list_open returns only incidents carrying open_bucket
- [ ] #3 Legacy item mapping covers the time, severity, product, role and reference cases, with references carrying system and tenant
- [ ] #4 An in-memory IncidentStore fake is exported for consumer tests
- [ ] #5 The RecordStore docstring and conformance suite state and check that an index query returns full items on both stores
- [ ] #6 No write operation is on IncidentStore, and the store docstring names the slices that add them
<!-- AC:END -->
