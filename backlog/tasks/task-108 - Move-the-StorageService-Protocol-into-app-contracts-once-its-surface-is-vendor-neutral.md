---
id: TASK-108
title: >-
  Move the StorageService Protocol into app/contracts/ once its surface is
  vendor-neutral
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
labels:
  - plugin-architecture
  - contracts
  - storage
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
decisions/plugin-architecture.md: the core-service Protocols (storage, queue, coordination, secrets, scheduler, translator, current user) live in app/contracts/, and their implementations in app/infrastructure/. Contracts expose no provider concept, so the DynamoDB-shaped query(key_condition: str) must be gone first. TASK-27.1 replaces it, which is why this move waits for it and does not move a leaky Protocol only to rewrite it.

Mechanical: the Protocol and its value types move; the DynamoDB implementation and the in-memory fake stay in app/infrastructure/storage/. Every importer is rewritten with no re-export. The coordination Protocol moves with its rename (TASK-58), and the queue Protocol is born in contracts (TASK-34).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The StorageService Protocol and its value types live in app/contracts/; app/infrastructure/storage/ keeps only implementations and imports the Protocol from contracts
- [ ] #2 No vendor type or DynamoDB expression string appears in the contracts module
- [ ] #3 grep finds no import of the Protocol at its old path and no re-export
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
