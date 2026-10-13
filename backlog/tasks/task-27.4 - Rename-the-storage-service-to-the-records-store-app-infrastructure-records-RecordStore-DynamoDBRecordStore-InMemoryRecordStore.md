---
id: TASK-27.4
title: >-
  Rename the storage service to the records store: app/infrastructure/records/,
  RecordStore, DynamoDBRecordStore, InMemoryRecordStore
status: To Do
assignee: []
created_date: '2026-10-13 13:34'
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
- [ ] #1 app/infrastructure/records/ holds RecordStore (protocol.py) and DynamoDBRecordStore with get_record_store() (service.py); app/infrastructure/storage/ no longer exists
- [ ] #2 The in-memory fake is InMemoryRecordStore and the storage tests live under tests/unit/infrastructure/records/ and tests/integration/infrastructure/records/
- [ ] #3 grep over app/ (excluding .venv) finds no StorageService, DynamoDBStorageService, get_storage_service or infrastructure.storage, and no re-export or alias of the old names
- [ ] #4 import-linter ignore entries name infrastructure.records with the same count as before; decisions/ current-state lists cite the new names
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
