---
id: TASK-27.1
title: >-
  Storage slice 1: vendor-neutral key-condition read, migrate the six query call
  sites, fake into the package
status: To Do
assignee: []
created_date: '2026-09-16 13:57'
updated_date: '2026-09-24 20:11'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies: []
references:
  - app/infrastructure/storage/protocol.py
  - app/infrastructure/audit/service.py
  - app/packages/access/request/store.py
  - decisions/cloud-portability.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: high
ordinal: 219000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-27 (see the coordinator plan). Pulled forward: this slice is disjoint from TASK-25.2.5 (different files) and can run in parallel with it rather than waiting for the rest of m-4.

WHY NOW. StorageService.query(table, key_condition: str, ...) leaks DynamoDB KeyConditionExpression through a Path A Protocol, the counterexample decisions/cloud-portability.md contract 4 names by hand. It has exactly six call sites today, in four files, and neither consumer is live in production: infrastructure/audit's service has no importer outside its own package (integrations/sentinel/client.py imports only audit.models), and packages/access is not enabled yet (TASK-25.2 scope note). This is the cheapest this change will ever be, and it gets more expensive with every new consumer: TASK-32, TASK-60, TASK-83, TASK-83.2, TASK-37.1 and TASK-38 all write against this Protocol.

THE SIX CALL SITES (read 2026-09-16)
- infrastructure/audit/service.py:151 resource_id = :rid, plus an optional AND timestamp_correlation_id < :ts; Limit, ScanIndexForward=False
- infrastructure/audit/service.py:192 user_email = :ue, plus an optional AND timestamp < :ts; IndexName user_email-timestamp-index, Limit, ScanIndexForward=False
- infrastructure/audit/service.py:221 correlation_id = :cid; IndexName correlation_id-index, Limit=1
- packages/access/request/store.py:133 PK = :pk AND begins_with(SK, :prefix)
- packages/access/request/store.py:183 PK = :pk
- packages/access/sync/store.py:72 PK = :pk; ScanIndexForward=False, Limit

SURFACE. Partition-key equality plus an optional sort-key condition, an optional index name, a limit and a forward flag. Sort conditions with a real consumer today are eq, lt and begins_with. gt and between are NOT added here: no caller needs them, and decisions/layers.md bars building Path A surface speculatively. between is what audit's currently unimplemented end_time parameter would need, so record it against audit rather than adding it blind.

NOT IN THIS SLICE. Atomic update, numeric increment and the bounded full-table list are TASK-27.2, which lands with its first consumer (TASK-37.1). Path A fake coverage for directory and audit plus the CI fake-coverage check are TASK-27.3.

FAKE. Move the existing FakeStorageService out of app/tests/unit/infrastructure/storage/fake_storage.py into the storage package itself, mirroring infrastructure/idempotency/in_memory.py, so the CI check TASK-27.3 wires reads the package tree. Update its importers (tests/unit/infrastructure/storage/test_storage_fake_storage.py, tests/unit/packages/access/sync/test_providers.py and anything the re-grep finds).

SIZE. About 165 production LOC: protocol.py ~35, service.py query ~40 changed, the six call sites ~50, the fake ~40 changed. Three directories (infrastructure/storage, infrastructure/audit, packages/access), which is at the edge of the two-subsystem rule; if review wants it tighter, split expand/migrate/contract, remembering the TASK-27 decision that no compat overload is retained in the end state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The StorageService read operation takes a typed, vendor-neutral key-condition spec (partition-key equality, optional sort-key condition, optional index name, limit, forward flag) and no signature on the Protocol contains a DynamoDB expression string, ExpressionAttributeValues or any other vendor type
- [ ] #2 Only sort-key conditions with a real consumer are implemented (eq, lt, begins_with); gt and between are recorded as deferred with the consumer that would need them, per decisions/layers.md on speculative Path A surface
- [ ] #3 All six existing call sites are migrated (infrastructure/audit/service.py x3, packages/access/request/store.py x2, packages/access/sync/store.py x1) and the raw-string query signature is deleted outright, with no compatibility overload retained
- [ ] #4 rg for KeyConditionExpression or ExpressionAttributeValues over app/ hits only infrastructure/storage/service.py and its own tests
- [ ] #5 The in-memory fake lives in the storage package (mirroring infrastructure/idempotency/in_memory.py), honours the new spec, and every former importer of tests/unit/infrastructure/storage/fake_storage.py is repointed
- [ ] #6 The conformance suite runs the same cases against the fake and the moto-backed DynamoDB implementation and passes on both
- [ ] #7 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). After this slice the StorageService Protocol moves to app/contracts/ (TASK-108).
---
<!-- COMMENTS:END -->
