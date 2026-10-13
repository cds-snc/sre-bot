---
id: TASK-27.4
title: >-
  Rename the storage service to the records store: app/infrastructure/records/,
  RecordStore, DynamoDBRecordStore, InMemoryRecordStore
status: Done
assignee:
  - '@me'
created_date: '2026-10-13 13:34'
updated_date: '2026-10-13 17:30'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies: []
references:
  - app/infrastructure/storage/protocol.py
  - app/infrastructure/storage/service.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: high
ordinal: 368000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app's persistence contract is named for what it holds, records, not for a storage medium: "storage" reads as blob or file storage and blurs against the files and documents workplace capabilities, and the role-naming rule in decisions/feature-packages.md rejects the Service suffix. The contract is the records contract and its Protocol is RecordStore.

Mechanical rename only, no behaviour change, landed before TASK-27.1 so every later slice and consumer is written against the final names:
- app/infrastructure/storage/ becomes app/infrastructure/records/ (protocol.py, service.py, __init__.py).
- StorageService becomes RecordStore; DynamoDBStorageService becomes DynamoDBRecordStore; get_storage_service() becomes get_record_store().
- The test fake in tests/unit/infrastructure/storage/fake_storage.py becomes InMemoryRecordStore; tests move to tests/unit/infrastructure/records/ and tests/integration/infrastructure/records/ with names following testing-standards.
- Importers rewritten with no re-export or alias: infrastructure/audit/service.py, packages/access/request/{providers,store}.py, packages/access/sync/{providers,store,job_status_store}.py, and their tests.
- The import-linter ignore entries in app/pyproject.toml that name infrastructure.storage are renamed, not widened.
- The current-state and tolerated lists in decisions/ that cite infrastructure/storage, StorageService or get_storage_service name the new paths.

DynamoDB table names, Terraform and settings keys are unchanged. Moving the Protocol into app/contracts/records/ stays with TASK-108, after TASK-27.1 makes its surface vendor-neutral.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/records/ holds RecordStore (protocol.py) and DynamoDBRecordStore with get_record_store() (service.py); app/infrastructure/storage/ no longer exists
- [x] #2 The in-memory fake is InMemoryRecordStore and the storage tests live under tests/unit/infrastructure/records/ and tests/integration/infrastructure/records/
- [x] #3 grep over app/ (excluding .venv) finds no StorageService, DynamoDBStorageService, get_storage_service or infrastructure.storage, and no re-export or alias of the old names
- [x] #4 import-linter ignore entries name infrastructure.records with the same count as before; decisions/ current-state lists cite the new names
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE AND GATE
Pure mechanical rename (no behaviour change). Production: 3 files git-moved (infrastructure/storage/{__init__,protocol,service}.py -> infrastructure/records/) + 6 edited (infrastructure/audit/service.py, packages/access/request/{providers,store}.py, packages/access/sync/{providers,store,job_status_store}.py) + app/pyproject.toml = 10 files, ~45 changed production lines (service.py is a pure move plus 6 lines). Tests: 7 moved/renamed + 3 edited in place. One subsystem (app/), one `git revert` restores. Gate verdict: passes (at the ~10 file line, but purely mechanical, no behaviour change, no expand/contract possible without leaving an alias, which the task forbids). No decomposition.

NOT FOUND (nothing to plan): no provider or Depends alias names storage (app/infrastructure/services/ does not exist; no providers/dependencies alias in app/server or app/api); no hits in terraform/, .github/, app/bin/, CLAUDE.md or .claude/; decisions/ already carry the 2026-10-13 'storage contract is the records contract (RecordStore, TASK-27.4)' lines and have no remaining infrastructure/storage, StorageService or get_storage_service text (verify with rg at the end; edit only if a hit appears). DynamoDB table names, Terraform and settings keys are untouched.

TDD ORDER (mechanical rename: tests first, fail on import, then production)
Step 1 - Move tests (git-mv by the human is not needed; the implementer moves files via the filesystem, no git commands) and rewrite them to the NEW names. Run pytest on the new dirs: they must fail at import (infrastructure.records does not exist). This red state is the proof the tests exercise the new path.
 a. app/tests/unit/infrastructure/storage/ -> app/tests/unit/infrastructure/records/ (add __init__.py):
    - fake_storage.py -> in_memory_record_store.py; class FakeStorageService -> InMemoryRecordStore; docstrings say 'record store'.
    - test_storage_service.py -> test_records_dynamodb_store_operations.py; classes TestStorageService* -> TestDynamoDBRecordStore*; test_get_storage_service_uses_integrations_get_aws_client -> test_get_record_store_uses_integrations_get_aws_client; patches get_record_store.cache_clear; module alias service_module -> infrastructure.records.service.
    - test_storage_protocol.py -> test_records_store_protocol_conformance.py; test_dynamodb_storage_satisfies_protocol -> test_dynamodb_record_store_satisfies_protocol; test_fake_storage_satisfies_protocol -> test_in_memory_record_store_satisfies_protocol; test_storage_service_dep_override_with_fake -> test_record_store_dep_override_with_fake; Depends(get_record_store).
    - test_storage_fake_storage.py -> test_records_in_memory_store_operations.py; test_fake_storage_* -> test_in_memory_record_store_*.
 b. app/tests/integration/infrastructure/storage/ -> app/tests/integration/infrastructure/records/ (add __init__.py):
    - conftest.py: fixture storage_service -> record_store; STORAGE_TEST_TABLE_NAME -> RECORDS_TEST_TABLE_NAME with value 'test-sre-bot-record-store' (moto-local table, not a real table); _create_storage_table -> _create_records_table; docstring and DynamoDBRecordStore import.
    - test_storage_service_conformance.py -> test_records_dynamodb_store_conformance.py; every storage_service param/arg -> record_store (about 35 occurrences, lines 24-101); class docstring DynamoDBRecordStore.
 c. Edit in place (not moved): tests/unit/infrastructure/audit/test_audit_protocol.py:18,77 (import + MagicMock(spec=RecordStore)); tests/unit/infrastructure/audit/test_service.py:4 (docstring); tests/unit/packages/access/sync/test_providers.py:151 (monkeypatch target 'get_record_store').
 d. Delete the old test directories including their __pycache__ leftovers so no storage directory remains.
 e. Small bug fixes in touched files: drop deprecated 'from __future__ import annotations' from the three moved test modules (fake, protocol test, fake test); verify green afterwards. Module-top-level imports only; no function-level imports (grep '^\s+(from|import) ' and '__import__|importlib' over touched files returned only the existing TYPE_CHECKING block and one docstring example).
Step 2 - Production rename. Create app/infrastructure/records/ with the moved files:
 - __init__.py: docstring 'Generic DynamoDB record store for feature packages'; exports RecordStore and get_record_store only; no alias or re-export of the old names.
 - protocol.py:13 class StorageService -> RecordStore; module docstring 'Protocol contract for the record store'.
 - service.py: imports at :21; class DynamoDBStorageService (:51) -> DynamoDBRecordStore; get_storage_service (:289) -> get_record_store returning RecordStore; docstrings at :1, :8, :52, :290, :293. Structured log event names are renamed with the contract: initialized_storage_service -> initialized_record_store, storage_* -> records_* (storage_put_ok -> records_put_ok, etc.). Nothing outside the repo consumes them; any test asserting an event name is updated with it.
 - delete app/infrastructure/storage/ entirely (incl. __pycache__).
Step 3 - Importers, rewritten with no alias:
 - infrastructure/audit/service.py:4,16,19,34,48,246 (get_record_store, RecordStore; attribute and kwarg 'storage' unchanged).
 - packages/access/request/providers.py:16,32; request/store.py:3,30,44,47,52.
 - packages/access/sync/providers.py:6,50,56; sync/store.py:3,19,29,32,37; sync/job_status_store.py:3,19,29 (also delete the deprecated 'from __future__ import annotations' at :11).
 - Constructor param/kwarg and attribute names 'storage' stay (renaming them churns about 40 test lines and TASK-27.1 rewrites these call sites anyway).
Step 4 - app/pyproject.toml import-linter ignores, renamed not widened, count stays 5: lines 278 and 297 'infrastructure.storage' -> 'infrastructure.records'; 291 'packages.access.sync.job_status_store -> infrastructure.records'; 282 and 298 '.. -> infrastructure.records.protocol'. Keep alphabetical order within each list (records sorts after i18n/idempotency and before security; verify ordering convention only if the list is sorted). unmatched_ignore_imports_alerting=error will fail lint-imports if any entry is stale or missed.
Step 5 - Verify decisions/ (rg for the old names returns nothing; already updated), then gates.

AC TRACEABILITY
 AC1 -> Steps 2,3 ; tests test_records_store_protocol_conformance.py (isinstance RecordStore, DynamoDBRecordStore), test_records_dynamodb_store_operations.py (get_record_store provider test); rg/ls check that app/infrastructure/storage is gone.
 AC2 -> Step 1 ; test_records_in_memory_store_operations.py and the protocol conformance test (InMemoryRecordStore satisfies RecordStore); integration conformance under tests/integration/infrastructure/records/.
 AC3 -> Steps 1-4 ; final 'rg -n "StorageService|DynamoDBStorageService|get_storage_service|infrastructure[./]storage|FakeStorage|fake_storage|storage_service" app --glob "!.venv/**"' returns no hits; rg -n '"storage_' over app/infrastructure/records returns no log event names.
 AC4 -> Step 4 (lint-imports green, 5 entries) and Step 5.
 AC5 -> verification block below.

TEST MATRIX (existing behaviour preserved; no new behaviour tests)
 Unit: put/put_if_not_exists/get/query/delete success, conditional-check rejection, SDK exception mapping (test_records_dynamodb_store_operations.py); Protocol runtime-check for DynamoDB store and fake, dependency_override with fake (test_records_store_protocol_conformance.py); fake put/get/query/delete (test_records_in_memory_store_operations.py). Integration (moto): roundtrip, missing key, conditional create, duplicate rejection, delete, query, paginated query (test_records_dynamodb_store_conformance.py). Consumers: audit and access sync/request tests pass unchanged apart from names. Test names follow test_<domain>_<entity>_<action>.py with domain 'records'.

VERIFICATION (from /workspace/app, report actual output)
 uv run ruff check .
 uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'   (no new errors in touched files)
 uv run lint-imports
 uv run pytest tests --ignore=tests/smoke
Red check before Step 2: uv run pytest tests/unit/infrastructure/records tests/integration/infrastructure/records fails with ModuleNotFoundError for infrastructure.records.

END-STATE CHECK
 - TASK-108 moves the RecordStore Protocol to app/contracts/records/ after TASK-27.1: it will be a one-file move of protocol.py plus import rewrites; the package name 'records' and class name RecordStore are already final, so no rename rework.
 - TASK-27.1 changes the surface and moves the fake into the package: InMemoryRecordStore already has its final name; only its location changes. The fake stays a test helper here (not in production code).
 - Every later consumer (webhooks, people, incident core, approvals) is written against RecordStore / get_record_store.

ASSUMPTIONS AND DOUBTS
 1. Log event names are not alerted on. Confirmed by the human: nothing outside the repo consumes them; rg over terraform and .github returned nothing.
 2. No other code references infrastructure.storage dynamically (strings, entry points, mock.patch targets). Verified by rg over app/ (excl .venv), decisions, terraform, .github, app/bin, CLAUDE.md, .claude; re-run after the edit.
 3. Import-linter sorted order is cosmetic; lint-imports (unmatched_ignore_imports_alerting=error) is the authority.
 4. mypy: baseline errors outside touched files are ignored; record 0 new in touched files.

BLAST RADIUS AND ROLLBACK
 Import-time break only (ModuleNotFoundError) if a reference is missed; caught by pytest, mypy and lint-imports. Runtime behaviour, DynamoDB tables, Terraform and settings are unchanged, so one revert of the PR fully restores the previous state. Must merge before TASK-27.1 so later slices use final names; no environment ordering constraints.

DECISIONS (reviewer, 2026-10-13)
- Log event names are renamed to the records vocabulary (no external consumers).
- The storage kwarg and _storage attributes in the audit service and access stores keep their names in this PR; TASK-27.1 rewrites those call sites.
- InMemoryRecordStore stays a test helper under tests/unit/infrastructure/records/ until TASK-27.1 moves it into the package.
- The moto-local test table is test-sre-bot-record-store.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed (mechanical rename, no behaviour change)
- app/infrastructure/storage/ moved to app/infrastructure/records/: StorageService -> RecordStore (protocol.py), DynamoDBStorageService -> DynamoDBRecordStore and get_storage_service -> get_record_store (service.py); __init__.py exports RecordStore and get_record_store only, no alias of the old names. Module docstrings name the record store.
- Structured log events renamed with the contract (reviewer decision, no external consumers): initialized_storage_service -> initialized_record_store, storage_* -> records_*.
- Importers rewritten: infrastructure/audit/service.py, packages/access/request/{providers,store}.py, packages/access/sync/{providers,store,job_status_store}.py. The storage kwarg and _storage attributes keep their names (reviewer decision; TASK-27.1 rewrites those call sites).
- app/pyproject.toml: the 5 import-linter ignore entries now name infrastructure.records / infrastructure.records.protocol (count unchanged at 5).
- Tests: tests/unit/infrastructure/records/ holds in_memory_record_store.py (InMemoryRecordStore), test_records_dynamodb_store_operations.py, test_records_store_protocol_conformance.py, test_records_in_memory_store_operations.py; tests/integration/infrastructure/records/ holds conftest.py (fixture record_store, moto table test-sre-bot-record-store) and test_records_dynamodb_store_conformance.py. Old storage test dirs deleted. In place: audit/test_audit_protocol.py, audit/test_service.py, access/sync/test_providers.py (monkeypatch target get_record_store).
- Deprecated 'from __future__ import annotations' removed from job_status_store.py and the three moved test modules.
- decisions/ already cited the new names; no edit needed.

TDD: tests were moved and rewritten first and failed with ModuleNotFoundError: No module named 'infrastructure.records' before the production move.

Evidence (from app/)
- uv run ruff check . -> All checks passed!
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files; 0 in touched files (all pre-existing elsewhere).
- uv run pytest tests --ignore=tests/smoke -> 4607 passed.
- rg for StorageService|DynamoDBStorageService|get_storage_service|infrastructure[./]storage|FakeStorage|fake_storage|storage_service and the old log event names over app (excl .venv), decisions, terraform, .github -> no hits.

Left for the human: code review; DynamoDB table names, Terraform and settings keys are unchanged so no deploy-side change is expected.
<!-- SECTION:NOTES:END -->
