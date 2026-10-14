---
id: TASK-108
title: >-
  Move the RecordStore Protocol into app/contracts/records/ once its surface is
  vendor-neutral
status: Done
assignee:
  - '@me'
created_date: '2026-09-24 19:58'
updated_date: '2026-10-14 16:10'
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
- [x] #1 The RecordStore Protocol and its value types live in app/contracts/records/; app/infrastructure/records/ keeps only implementations and imports the Protocol from contracts
- [x] #2 No vendor type or DynamoDB expression string appears in the contracts module
- [x] #3 grep finds no import of the Protocol at its old path and no re-export
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #5 InMemoryRecordStore and DynamoDBRecordStore explicitly subclass the moved contracts RecordStore, so make check-fake-coverage covers it by the contracts rule and the records conformance enrollment test stays green
- [x] #6 The three import-linter ignore entries the move fixes (packages.access.request.store, packages.access.sync.store, packages.access.sync.job_status_store) are removed
- [x] #7 The value-type tests live under app/tests/unit/contracts/records/
- [x] #8 The import-linter shrink-only comment in contract (b) admits a named exception: an entry recorded on an approved task with the task that removes it (TASK-145.5's get_record_store wiring, removed by TASK-109)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Pure move, no signature or behavior change. Approved 2026-10-14 (option A): one module app/contracts/records/store.py holding the whole surface, plus a package __init__ that re-exports all of it, helpers included, following the contracts.operations precedent (149 call sites import from the package root).

Steps
1. Tests first (red). Move tests/unit/infrastructure/records/test_records_query_spec.py and test_records_store_update_validation.py to tests/unit/contracts/records/ (new __init__.py) and import from contracts.records. The vendor-vocabulary test reads contracts.records.store and also bans UpdateExpression, ConditionExpression and attribute_not_exists, which TASK-27.2 made relevant. Add tests/unit/contracts/records/test_records_contracts_imports.py: an AST scan proving every import in contracts/records/*.py is stdlib or contracts.* (same pattern as test_scheduler_contracts_registry_protocol.py), and contracts.records.__all__ equals the moved public names. Rewrite the enrollment test import to contracts.records. Expected first run: ModuleNotFoundError for contracts.records.
2. Create app/contracts/records/__init__.py (re-exports and __all__) and move infrastructure/records/protocol.py to contracts/records/store.py unchanged apart from its docstring. Moved: KeyValue, KeySchema, RecordIndex, RecordTable, SortOperator, SortOrder, SortCondition, RecordQuery, resolve_query_key, SetAttribute, RemoveAttribute, IncrementAttribute, RecordChange, ExpectedValue, validate_record_update, RecordStore. Its only app import is contracts.operations.result, which contract (c) allows.
3. Infrastructure: infrastructure/records/__init__.py drops the protocol re-exports and keeps get_record_store only (docstring updated). in_memory.py:10, service.py:8 (docstring) and :23, and audit/service.py:18 import from contracts.records. InMemoryRecordStore (in_memory.py:60) and DynamoDBRecordStore (service.py:142) keep subclassing RecordStore explicitly, now the contracts one.
4. Packages: access/request/store.py:30, access/sync/store.py:19 and access/sync/job_status_store.py:17 import the types from contracts.records. The providers keep get_record_store from infrastructure.records.
5. pyproject.toml, import-linter contract (b): remove the three entries the move fixes (packages.access.request.store -> infrastructure.records.protocol, packages.access.sync.store -> infrastructure.records.protocol, packages.access.sync.job_status_store -> infrastructure.records). unmatched_ignore_imports_alerting = "error" makes this mandatory. Both providers entries stay. The contract (b) shrink-only comment gains one named exception: an entry recorded on an approved task, naming the task that removes it (TASK-145.5's get_record_store wiring, removed by TASK-109; TASK-109 AC #8 tracks it).
6. Remaining test imports to rewrite (types from contracts.records; implementations stay at their path): tests/integration/infrastructure/records/conftest.py:16, test_records_store_query_conformance.py:12, test_records_store_update_conformance.py:20, tests/unit/infrastructure/audit/test_audit_protocol.py:18, test_audit_settings_table_name.py:15, tests/unit/infrastructure/records/test_records_dynamodb_store_operations.py:14, test_records_in_memory_store_operations.py:12, test_records_store_protocol_conformance.py:11, test_records_store_update_expression.py:17, tests/unit/packages/access/common/test_access_settings_table_names.py:15.
7. Docs (approved): the current-state path in decisions/approvals.md:19 and :72 and decisions/people-and-accounts.md:22.
8. Gates: ruff, mypy, lint-imports, pytest tests --ignore=tests/smoke, make check-fake-coverage, then grep -rn "infrastructure.records.protocol\|from infrastructure.records import .*Record" app/ returns nothing.

AC traceability
- AC1 -> steps 2-4; tests: moved value-type suites under tests/unit/contracts/records/, test_records_contracts_imports.py (__all__).
- AC2 -> step 2; tests: vendor-vocabulary test on contracts.records.store, the AST import scan; import-linter contract (c).
- AC3 -> steps 3, 4, 6; evidence: grep in step 8, and infrastructure/records/__init__.py has no protocol names.
- AC4 -> step 8.
- AC6 -> step 5; evidence: lint-imports green with the entries gone.
- AC7 -> step 1.
- AC8 -> step 5; evidence: the comment text in pyproject.toml.
- AC5 -> step 3; tests: test_records_store_conformance_enrollment.py against contracts RecordStore; make check-fake-coverage lists no contracts/records gap and baselines nothing new.

Test matrix
- Happy path: contracts.records exports the moved names; both implementations pass the query and update conformance suites unchanged.
- Boundary: contracts/records imports only stdlib and contracts.*; the source has no vendor vocabulary.
- Failure: the existing resolve_query_key and validate_record_update error cases keep passing at their new location.
- Enrollment: concrete_production_subclasses(contracts RecordStore) equals the fixture list.

Assumptions to verify in the first red run
- No string path references infrastructure.records.protocol (mock.patch targets, pickles). The grep found only imports and one inspect.getsource on the module object, which moves with the test.
- check_fake_coverage classifies contracts/records/store.py:RecordStore by the contracts rule, because both classes name RecordStore as an explicit base.
- concrete_production_subclasses still finds both implementations through the contracts class.
- lint-imports flags exactly the three entries in step 5 as unmatched after the move.

Size gate: about 9 production Python files plus pyproject.toml (and 2 ADRs if step 7 is approved). Hand-written LOC is about 60 (imports, the __init__, docstrings). The 234-line module is a git rename. One mechanical concern with no behavior change. It passes.

Blast radius and rollback: import-only. A missed importer fails at import time in pytest and mypy, not at runtime in production. One git revert restores the old path. Nothing depends on ordering: no Terraform, environment or CI change.

Downstream fit: TASK-109 registers the factory keyed by contracts.records.RecordStore. TASK-58 follows the same shape (contracts/coordination/ with package re-exports). TASK-145.5 and TASK-147.2 import types from contracts.records with no import-linter entry; only get_record_store needs the single tolerated entry until TASK-109.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14 implementation (pure move, no signature or behavior change)

What changed
- infrastructure/records/protocol.py moved to contracts/records/store.py (git mv, content unchanged). The new contracts/records/__init__.py re-exports the whole surface, helpers included.
- infrastructure/records/__init__.py now exports only get_record_store. in_memory.py, service.py and audit/service.py import from contracts.records. InMemoryRecordStore and DynamoDBRecordStore still subclass RecordStore explicitly, now the contracts class.
- packages/access request/store.py, sync/store.py and sync/job_status_store.py import from contracts.records.
- pyproject.toml, contract (b): removed the three ignore entries the move fixed. The shrink-only comment now admits one named exception, TASK-145.5's get_record_store wiring, which TASK-109 removes (TASK-109 AC #8).
- Tests: test_records_query_spec.py and test_records_store_update_validation.py moved to tests/unit/contracts/records/. The vendor-vocabulary list adds UpdateExpression, ConditionExpression and attribute_not_exists. New: test_records_contracts_imports.py (package __all__ and an AST scan for stdlib-only plus contracts imports). The enrollment test and 10 other test files import from contracts.records. In test_bin_fake_coverage_check.py, the no-gap assertion now names contracts/records/store.py:RecordStore.
- ADRs: updated the current-state paths in decisions/approvals.md:19 and decisions/people-and-accounts.md:22. approvals.md:72 is still accurate because get_record_store stays in infrastructure.records.

Assumptions verified in the red run
- The red run failed with ModuleNotFoundError: contracts.records in the 4 rewritten or new test modules.
- After the move, lint-imports reported exactly the three planned entries as unmatched.
- One path string the plan missed: tests/unit/bin/test_bin_fake_coverage_check.py:329, updated to the new path. This was within scope and needed no AC change.

Evidence
- uv run ruff check .: All checks passed.
- uv run lint-imports: Contracts 10 kept, 0 broken.
- make check-fake-coverage: OK, 6 baselined gaps, no records entry.
- uv run pytest tests --ignore=tests/smoke: 4781 passed.
- uv run mypy: 48 errors, all in legacy modules/ files and none in touched files.
- A grep for infrastructure.records.protocol, and for type imports from infrastructure.records, returns nothing. A grep for vendor vocabulary in contracts/records returns nothing.

For the human: review the PR, confirm git shows protocol.py -> contracts/records/store.py as a rename, and move the task to Done after merge.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-13 19:59
---
2026-10-13 records/incidents layout decision: TASK-27.2 adds the change-set types (frozen dataclasses) and the shared update validation helper to protocol.py before this move; it stays a pure move with no signature change, and the new types move with the rest. No vendor expression in the contract.
---
<!-- COMMENTS:END -->
