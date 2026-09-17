---
id: TASK-103
title: Make StorageService.put_if_not_exists replay-safe against its own SDK retry
status: To Do
assignee: []
created_date: '2026-09-17 20:40'
updated_date: '2026-09-17 20:47'
labels:
  - infrastructure
  - reliability
  - phase-4
milestone: m-4
dependencies:
  - TASK-25.2.5.4
references:
  - app/infrastructure/storage/service.py
  - decisions/layers.md
priority: low
ordinal: 231000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Repoints a dangling pointer found while planning TASK-25.2.5.4 on 2026-09-17.

TASK-25.2.5's implementation notes park this hazard with the words "infrastructure/storage/service.py:138 put_if_not_exists has the same self-replay hazard, but it has no production caller today, so no action; it will be relevant to TASK-27." Verified 2026-09-17 that neither TASK-27 nor any of TASK-27.1/27.2/27.3 mentions put_if_not_exists as a replay hazard - TASK-27.2 names the method only as an existing Protocol operation. The pointer goes nowhere, so the finding lives in one task's notes and would be lost when that task closes.

THE HAZARD, identical in shape to the one TASK-25.2.5.4 fixes for the idempotency claim: put_if_not_exists issues a conditional PutItem on a retrying client. If the first attempt lands but its response is lost, botocore resends the identical serialized body, the condition now fails, and the caller is told the key already existed when in fact it had just created it.

STILL TRUE AS OF 2026-09-17: no production caller. That is why this is filed rather than fixed. It becomes live the moment a caller appears - TASK-37.1's WebhookStore and TASK-83.2's multi-item conditional write are the nearest candidates - so the fix should land with the first real consumer, not speculatively (decisions/layers.md: Path A capabilities are not built ahead of a consumer).

FIX SHAPE: whatever TASK-25.2.5.4 settles on for the idempotency claim, applied here - an opaque per-call owner token written into the item and compared on the re-read. Portability was reviewed 2026-09-17 and the pattern carries to Redis, Postgres and Cosmos unchanged. Read that task's implementation before re-deriving anything.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 put_if_not_exists does not report an existing key when the key was created by this call's own retried write
- [ ] #2 The behaviour is covered by a test at the same level as the idempotency store's claim-token tests
- [ ] #3 If the method still has no production caller when this is picked up, that is recorded and the task is deferred again rather than implemented speculatively
<!-- AC:END -->
