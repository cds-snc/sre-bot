---
id: TASK-27.5
title: 'Records: bounded or paginated full-table read, shaped with its first consumer'
status: To Do
assignee: []
created_date: '2026-10-13 19:59'
updated_date: '2026-10-19 15:27'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.2
references:
  - decisions/plugin-architecture.md
  - decisions/webhooks.md
  - 'https://github.com/cds-snc/sre-bot/issues/1607'
parent_task_id: TASK-27
priority: medium
ordinal: 379000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-27.2 so the full-table read is shaped with a real consumer instead of ahead of it (decisions/plugin-architecture.md: capabilities are never built speculatively).

CONSUMERS. TASK-145.5.7 (first, 2026-10-14): the incident legacy upgrade job reads every incidents item once; Stack K layer 12, with this task as layer 11 directly below it. TASK-37.1: the webhook store's list and lookup, today full-table DynamoDB scans over a small configuration-sized table. TASK-145.12: rebuilding the incident list sheet from the incidents table, which is unbounded and may want a paginated read rather than a capped list.

OPEN SHAPE, decided when the first consumer is planned: a capped list(table, limit) versus a paginated or iterating read. If capped, exceeding the cap is an error result, never a silent truncation (a lookup that silently misses a row is a correctness and security bug), and the cap is a documented setting with a default, not a hardcoded constant.

CONSTRAINTS. Every operation takes table: RecordTable. No filter expression, projection or scan parameter appears in any Protocol signature; client-side filtering belongs to the caller. Table names come from the owning package's settings; the key layout stays in code. DynamoDB paginates Scan internally; the fake and the DynamoDB store pass the same conformance cases, including the over-cap or multi-page case. Two-provider check: DynamoDB Scan, Cosmos DB cross-partition query, Postgres SELECT with LIMIT, Firestore collection read.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The first consumer's need decides the shape (capped list or paginated read), recorded in the plan with the other consumer's need considered
- [ ] #2 Past a cap, if one exists, the result is an error and never a truncated success; the cap comes from a documented setting with a default
- [ ] #3 No filter, projection or scan parameter and no vendor type appears in the Protocol signature; every call takes table: RecordTable
- [ ] #4 The in-memory fake and the DynamoDB store pass the same conformance cases on the fake and moto, including a result larger than one backend page
- [ ] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: pulled forward into Stack K (handoff doc-13) as layer 8; TASK-145.5.7 is the first consumer and depends on this task. The shape is still decided at planning, with TASK-37.1 and TASK-145.12 considered.

2026-10-19: Stack K layer 11 after TASK-145.5.5 was split into TASK-145.5.9, TASK-145.5.10 and the cutover (layers 7 to 9).
<!-- SECTION:NOTES:END -->
