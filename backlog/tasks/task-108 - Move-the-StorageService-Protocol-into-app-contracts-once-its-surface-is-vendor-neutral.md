---
id: TASK-108
title: >-
  Move the RecordStore Protocol into app/contracts/records/ once its surface is
  vendor-neutral
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
updated_date: '2026-10-13 19:59'
labels:
  - plugin-architecture
  - contracts
  - records
milestone: m-7
dependencies:
  - TASK-106
  - TASK-27.1
references:
  - decisions/plugin-architecture.md
  - decisions/cloud-portability.md
priority: medium
type: task
ordinal: 250000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: the core-service Protocols (records, queue, coordination, secrets, scheduler, translator, current user) live in app/contracts/, and their implementations in app/infrastructure/. Contracts expose no provider concept, so the Protocol had to be vendor-neutral first. TASK-27.1 made it so (every method takes a RecordTable; reads take a typed RecordQuery), which is why this move waits for it and does not move a leaky Protocol only to rewrite it.

Mechanical, a pure move of app/infrastructure/records/protocol.py: the RecordStore Protocol and its value types (KeyValue, KeySchema, RecordIndex, RecordTable, SortOperator, SortOrder, SortCondition, RecordQuery) plus the resolve_query_key helper move to app/contracts/records/ with no signature change; the DynamoDB implementation and the in-memory fake stay in app/infrastructure/records/. Every importer is rewritten with no re-export. The coordination Protocol moves with its rename (TASK-58), and the queue Protocol is born in contracts (TASK-34).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The RecordStore Protocol and its value types live in app/contracts/records/; app/infrastructure/records/ keeps only implementations and imports the Protocol from contracts
- [ ] #2 No vendor type or DynamoDB expression string appears in the contracts module
- [ ] #3 grep finds no import of the Protocol at its old path and no re-export
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 (TASK-140.4): packages.incident.core.adapters.status_updates is a second interim direct-boto3 store (after TASK-140.3's legacy lookup) waiting on this Protocol; its migration is tracked on TASK-38.1. It needs conditional put with ReturnValuesOnConditionCheckFailure=ALL_OLD semantics and a descending, limited key query from the vendor-neutral surface.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-13 19:59
---
2026-10-13 records/incidents layout decision: TASK-27.2 adds the change-set types (frozen dataclasses) and the shared update validation helper to protocol.py before this move; it stays a pure move with no signature change, and the new types move with the rest. No vendor expression in the contract.
---
<!-- COMMENTS:END -->
