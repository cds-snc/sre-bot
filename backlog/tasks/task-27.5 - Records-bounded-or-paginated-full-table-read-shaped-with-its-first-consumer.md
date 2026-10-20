---
id: TASK-27.5
title: 'Records: bounded or paginated full-table read, shaped with its first consumer'
status: In Progress
assignee: []
created_date: '2026-10-13 19:59'
updated_date: '2026-10-20 19:01'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.2
references:
  - decisions/webhooks.md
  - 'https://github.com/cds-snc/sre-bot/issues/1607'
  - decisions/cloud-portability.md
  - 'https://google.aip.dev/158'
  - 'https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html'
parent_task_id: TASK-27
priority: medium
ordinal: 379000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-27.2 so the full-table read is shaped with a real consumer instead of ahead of it (decisions/cloud-portability.md contract 4: a fake is required only where the Protocol has a real consumer; capabilities are never built speculatively).

CONSUMERS. TASK-145.5.7 (first, 2026-10-14): the incident legacy upgrade job reads every incidents item once, completely, before any write; Stack K, built on this task once it merges (this task is a single PR from main, human 2026-10-20). TASK-37.1: the webhook store's list and lookup, today full-table DynamoDB scans over a small configuration-sized table. TASK-145.12: the projection rebuild job regenerates the incident list sheet from every record (its listings read the open index, not a full read; AC3 rewritten 2026-10-20).

SHAPE (decided 2026-10-20, human, after a review of the ADRs, doc-11 and industry guidance: Google AIP-158, the DynamoDB Scan guide, batch-iteration idioms): a capped list, RecordStore.read_all(table, *, max_items) -> OperationResult[list[dict]]. Every item, or an error result past max_items, never a truncated success. Strongly consistent as of the read's start (DynamoDB ConsistentRead), order unspecified. max_items is the caller's expectation of the table's size and comes from the owning package's settings (<SLICE>__<FIELD> with a default), like table names; incident core's setting lands with TASK-145.5.7. A whole-table read is for batch jobs and configuration-sized tables and is never a lookup or a listing: lookups go through declared indexes and a user-facing listing pages on an index query. A paginated read is a new operation added when a batch outgrows its cap (additive, so AIP-158's backward-compatibility concern does not apply to this internal Protocol). The rule is recorded in decisions/cloud-portability.md contract 4.

CONSTRAINTS. Every operation takes table: RecordTable. No filter expression, projection or scan parameter appears in any Protocol signature; client-side filtering belongs to the caller. Table names come from the owning package's settings; the key layout stays in code. DynamoDB paginates Scan internally (1 MB pages); the fake and the DynamoDB store pass the same conformance cases, including the over-cap and multi-page cases. Two-provider check: DynamoDB Scan with ConsistentRead, Cosmos DB cross-partition query, Postgres SELECT with LIMIT max_items+1, Firestore collection read with limit(max_items+1).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The shape is a capped list, RecordStore.read_all(table, *, max_items), decided with TASK-145.5.7 (first consumer), TASK-37.1 and TASK-145.12 considered, and recorded in the description and plan
- [x] #2 max_items is a required argument (below 1 raises ValueError); past it the result is a PERMANENT_ERROR with error code RECORD_READ_LIMIT_EXCEEDED and no data, never a truncated success; the read is strongly consistent and its order unspecified, both stated in the contract; the cap's setting belongs to each consumer's package (TASK-145.5.7 AC6, TASK-37.1)
- [x] #3 No filter, projection or scan parameter and no vendor type appears in the Protocol signature; every call takes table: RecordTable
- [x] #4 The in-memory fake and the DynamoDB store pass the same conformance cases on the fake and moto, including a result larger than one backend page
- [x] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
- [x] #6 decisions/cloud-portability.md contract 4 states the whole-table read rule (batch jobs and configuration-sized tables only, never a lookup or listing; all or an error past the caller's cap from its settings; strongly consistent, unordered; paged reads added as a new operation with their consumer), with a dated Changes line and its sources
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded on main fd90c402. Layer 10 (#1735) adds one bullet to the RecordStore update docstring in contracts/records/store.py, a separate hunk from this task's edit of the closing paragraph, so either merge order rebases cleanly. Single PR, not stacked (human, 2026-10-20: it builds on no Stack K layer; doc-2 "changes that don't depend on each other ship as parallel single PRs"), branch task-27.5-records-read-all from an up-to-date main. No consumer in this PR; the first is TASK-145.5.7 (Stack K, built on this once merged).

## Decision (human, 2026-10-20)
Capped list: RecordStore.read_all(table, *, max_items) -> OperationResult[list[dict]]. Every item, or PERMANENT_ERROR with error code RECORD_READ_LIMIT_EXCEEDED past max_items (never truncated). Strongly consistent as of the read's start; order unspecified. The cap is the caller's, from its package settings. Paginated cursor read rejected for now: no consumer needs it (cloud-portability.md contract 4 anti-speculative rule); added later as a new operation, so read_all is never changed. Sources: Google AIP-158 (truncation by a later default page size is the breaking change; fetch-all is reasonable for small collections), DynamoDB Scan guide (Scan eventually consistent by default, ConsistentRead includes every write completed before the scan began, 2x read cost; 1 MB pages; arbitrary order; design indexes so lookups use Query).

## Steps
1. ADR (first commit on the branch, planning refinement): decisions/cloud-portability.md contract 4, after the RecordStore worked example, a "Whole-table reads" paragraph: read_all serves batch jobs and configuration-sized tables, never a lookup (declared index) or a user-facing listing (an index query with paging); all items or an error past max_items, never truncated; max_items is the caller's expectation of the table size from its package settings (<SLICE>__<FIELD>, default), like table names; strongly consistent as of the read's start, order unspecified; a paged read is a new operation added with the batch that outgrows its cap. Sources AIP-158 and the DynamoDB Scan guide. Changes line: "2026-10-20: whole-table reads are capped all-or-error, strongly consistent and never a lookup or listing (TASK-27.5)."
2. app/contracts/records/store.py:
   - READ_LIMIT_EXCEEDED = "RECORD_READ_LIMIT_EXCEEDED" (error code constant) and validate_read_limit(max_items) raising ValueError below 1 (a caller programming error, like RecordQuery.limit).
   - RecordStore.read_all(self, table: RecordTable, *, max_items: int) -> OperationResult. Protocol docstring: replace "A bounded full-table read is a separate operation, added with its first consumer." with the read_all semantics (above), stating it reads the table only (no index), returns full items without store bookkeeping, and that a caller filters client-side.
   - Module docstring: one line on whole-table reads.
3. app/contracts/records/__init__.py: export READ_LIMIT_EXCEEDED and validate_read_limit.
4. app/infrastructure/records/in_memory.py: read_all validates, snapshots the table's items under the lock (deepcopy), returns the over-cap error when len > max_items, else success with the list. Class docstring mentions the capped whole-table read.
5. app/infrastructure/records/service.py: read_all validates, runs the scan paginator with TableName, ConsistentRead=True and PaginationConfig MaxItems = max_items + 1 (stops paging as soon as the cap is exceeded), deserializes (drops the write token). Over cap: log records_read_all_limit_exceeded (warning; table, operation, max_items) and return the error. SDK errors: classified via _map_sdk_exception, logged records_read_all_error (table, operation, max_items, error, error_code). Success: debug records_read_all_ok (table, count).

## Tests (written first, failing)
- tests/integration/infrastructure/records/test_records_store_read_all_conformance.py (any_record_store, fake and moto):
  happy: empty table -> []; items over several partitions and sort keys all returned (compared as sets, order unspecified); an item created by put_if_not_exists comes back without store bookkeeping (no _rs_ attribute); an item written then read is included.
  boundary: exactly max_items items -> success with all; max_items + 1 -> PERMANENT_ERROR, error_code RECORD_READ_LIMIT_EXCEEDED, data None.
  multi-page: five items of 350 KB (1.75 MB, three moto pages, verified empirically on moto 5.2.2) -> all five returned with max_items 5; max_items 4 -> the limit error.
  failure: max_items 0 raises ValueError on both stores.
- tests/unit/infrastructure/records/test_records_dynamodb_store_read_all.py (botocore Stubber, like the replay suite): the Scan request carries TableName and ConsistentRead=True and no FilterExpression, ProjectionExpression, IndexName or Segment; a LastEvaluatedKey page is followed with ExclusiveStartKey; paging stops once max_items + 1 items are seen (no further request queued); a ResourceNotFoundException is returned as a classified error with its error code; ProvisionedThroughputExceededException maps to TRANSIENT_ERROR.
- tests/unit/contracts/records/test_records_read_limit_validation.py: validate_read_limit rejects 0 and negatives, accepts 1.
- tests/unit/contracts/records/test_records_contracts_imports.py: PUBLIC_NAMES gains the two new exports (edited in place).

## AC traceability
AC1 -> description and this plan (Decision). AC2 -> steps 2, 4, 5 -> boundary and validation tests, contract docstring. AC3 -> step 2 signature (table, max_items only) -> review plus the Stubber request-shape test. AC4 -> steps 4, 5 -> conformance suite including multi-page. AC5 -> gates (make check-* and make test) in notes. AC6 -> step 1.
Tests -> AC: conformance -> AC2, AC4; Stubber -> AC2, AC3; validation -> AC2; imports -> AC3.

## Size gate
Production: 4 code files (store.py about +35, __init__.py +4, in_memory.py about +15, service.py about +45) plus one ADR paragraph and one Changes line. About 100 production LOC, one subsystem (records contract), no behaviour change for any existing caller. Passes.

## Assumptions and doubts
- moto honours ConsistentRead and the 1 MB page (page split verified 2026-10-20 on moto 5.2.2; ConsistentRead accepted, behaviour identical locally).
- MaxItems = max_items + 1 makes botocore stop requesting pages once the cap is exceeded; verified by the Stubber test (no extra page stubbed).
- IAM: no change. terraform/iam.tf:43 already grants dynamodb:Scan on every table in local.dynamodb_table_arns (incidents and webhooks included); the scan reads the table, never an index, so the /index/* statement is untouched.

## Blast radius and rollback
Additive: a new Protocol method and two implementations; no caller until TASK-145.5.7. A wrong implementation can only affect that job, which ships off. One git revert restores the previous contract. Merges on its own once approved; no ordering with Stack K.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-20 on task-27.5-records-read-all (from main a2b65676), TDD: the new and extended tests failed at collection (ImportError on READ_LIMIT_EXCEEDED, validate_read_limit, read_all) before any production edit.

Changes
- decisions/cloud-portability.md contract 4: "Whole-table reads" paragraph (batch jobs and configuration-sized tables only, never a lookup or listing; all or an error past the caller's cap from its settings; strongly consistent as of the read's start; unordered; a paged read is a new operation) with AIP-158 and DynamoDB sources, and a 2026-10-20 Changes line. [AC6]
- contracts/records/store.py: READ_LIMIT_EXCEEDED ("RECORD_READ_LIMIT_EXCEEDED"), validate_read_limit (ValueError below 1), RecordStore.read_all(table, *, max_items) and its Protocol docstring rules, replacing "added with its first consumer"; module docstring line. contracts/records/__init__.py exports both names. [AC2, AC3]
- infrastructure/records/in_memory.py: read_all snapshots the table under the lock, error past the cap, deep copies. [AC4]
- infrastructure/records/service.py: read_all runs the scan paginator with TableName, ConsistentRead=True and PaginationConfig MaxItems=max_items+1 (stops paging one item past the cap), deserializes (drops the write token), logs records_read_all_limit_exceeded (warning), records_read_all_error (error) and records_read_all_ok (debug) with table, operation, max_items. [AC2, AC4]
- No IAM change: terraform/iam.tf:43 already grants dynamodb:Scan on every table.

Tests
- tests/integration/infrastructure/records/test_records_store_read_all_conformance.py (fake and moto): empty table, every partition returned (set compare), no bookkeeping attributes, writes and deletes before the read reflected, exactly at cap, over cap is PERMANENT_ERROR + RECORD_READ_LIMIT_EXCEEDED + no data, five 350 KB items over three moto pages read whole and over-cap at 4, cap below 1 raises. [AC2, AC4]
- tests/unit/infrastructure/records/test_records_dynamodb_store_read_all.py (Stubber): Scan request is exactly TableName + ConsistentRead (+ ExclusiveStartKey on page 2), so no filter, projection, index or segment; paging stops after the over-cap page (no second page stubbed); ResourceNotFoundException classified and logged; throttling is TRANSIENT_ERROR. [AC2, AC3]
- tests/unit/contracts/records/test_records_read_limit_validation.py; in place: test_records_query_spec.py (read_all signature is self, table, max_items with table: RecordTable; ConsistentRead, ExclusiveStartKey, Segment added to the vendor-vocabulary ban) and test_records_contracts_imports.py (two new exports). [AC2, AC3]

Gates (from app/) [AC5]
- make lint-ci: rc 0; ruff "All checks passed!"; mypy 48 errors in 19 files, all pre-existing legacy (modules/...), 0 in touched files (rg over contracts/records, infrastructure/records and the three test dirs: no match).
- make fmt-ci: "984 files already formatted".
- make check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam, check-runtime-imports: OK. make check-import-contracts: "Contracts: 12 kept, 0 broken". make check-fake-coverage: "OK: every covered Protocol has an in-memory fake (6 baselined gap(s) remain)".
- make test: "4622 passed" and "772 passed".
- Records suites alone: 225 passed.

Follow-ups owned elsewhere: the cap setting INCIDENT_CORE__FULL_READ_MAX_ITEMS is TASK-145.5.7 AC6; the webhooks cap is TASK-37.1. Layer 10 (#1735) edits another hunk of the RecordStore docstring; either merge order rebases cleanly.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-20 18:54
---
2026-10-20 (human): plan approved; branch task-27.5-records-read-all cut from main a2b65676 after #1734 merged (single PR, not a Stack K layer).
---
<!-- COMMENTS:END -->
