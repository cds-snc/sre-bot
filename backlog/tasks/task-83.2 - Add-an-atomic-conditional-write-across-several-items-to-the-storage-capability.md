---
id: TASK-83.2
title: Add an atomic conditional write across several items to the storage capability
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:06'
labels:
  - identity
  - storage
dependencies:
  - TASK-27
  - TASK-108
references:
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - app/infrastructure/storage/protocol.py
parent_task_id: TASK-83
priority: medium
ordinal: 169000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/people-and-accounts.md (Draft) requires each account to be claimed by exactly one person, with the claim and the link written atomically. decisions/reliability.md already relies on the same shape: a marker and an entity in one transactional write.

StorageService (app/infrastructure/storage/protocol.py) offers only put, put_if_not_exists, get, query and delete. No package can write several items atomically today.

This is a hosting-storage primitive with no identity vocabulary. It builds on the capability-shaped redesign in TASK-27.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The storage capability exposes one operation that writes several items atomically, each with an optional condition: the item must not exist, or an attribute must equal an expected value
- [ ] #2 When any condition fails, nothing is written, and the result reports a conflict status distinct from errors that identifies the failing item
- [ ] #3 The DynamoDB implementation and the in-memory fake pass the same conformance tests, including a partial-conflict case
- [ ] #4 The operation's contract names no DynamoDB syntax
- [ ] #5 Full test suite, ruff and mypy pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25: decisions/workplace-systems.md, people-and-accounts.md and platform-entrypoints.md are Accepted. Earlier mentions of their Draft status in this task are historical. The atomic claim now covers IdP identities as well as platform accounts: each identity and each account is claimed by exactly one person, with the claim and its link in one conditional write.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:08
---
2026-09-24: the storage Protocol moves to app/contracts/ (TASK-108, decisions/plugin-architecture.md). This ticket adds the atomic multi-item write to it there, after the move, so the Protocol is not changed in two homes.
---
<!-- COMMENTS:END -->
