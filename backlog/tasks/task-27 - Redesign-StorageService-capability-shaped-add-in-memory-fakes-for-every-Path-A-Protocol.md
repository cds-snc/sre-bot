---
id: TASK-27
title: >-
  Redesign StorageService capability-shaped; add in-memory fakes for every Path
  A Protocol
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies: []
references:
  - decisions/cloud-portability.md
  - decisions/layers.md
  - 'https://github.com/cds-snc/sre-bot/issues/1281'
priority: high
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/cloud-portability.md contract 4. Today StorageService.query(table, key_condition: str, ...) in app/infrastructure/storage/protocol.py takes DynamoDB KeyConditionExpression strings - vendor query syntax leaking through the Protocol, the exact trap the decisions name. A Protocol that cannot be faithfully faked fails the contract.

Steps:
1. Redesign the StorageService surface in capability terms (typed key/attribute conditions or purpose-named methods like get_items_by_partition) such that an in-memory fake and a future Cosmos/Postgres backend can honor it without consumer changes. Design sketch reviewed before implementation (paste in the task notes).
2. Migrate the DynamoDB implementation and all consumers.
3. Write in-memory fakes for every Path A Protocol currently defined (storage, directory, idempotency - task-5 already delivered idempotency; audit, resilience as applicable) and use them in the integration test suite as the standing second provider.
4. Add a conformance test suite per Protocol run against both fake and real implementation (DynamoDB-Local marked slow).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 StorageService signatures contain no vendor query strings or vendor types; grep KeyConditionExpression appears only inside the DynamoDB implementation
- [ ] #2 Every app/infrastructure/<service>/ Path A package contains a fake exercised by tests (decisions/cloud-portability.md check)
- [ ] #3 Conformance suites pass against fake and DynamoDB implementations
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All consumers migrated; tests green
- [ ] #2 PR references decisions/cloud-portability.md
<!-- DOD:END -->
