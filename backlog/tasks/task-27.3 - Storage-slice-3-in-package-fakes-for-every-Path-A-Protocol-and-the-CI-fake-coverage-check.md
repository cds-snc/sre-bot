---
id: TASK-27.3
title: >-
  Storage slice 3: in-package fakes for every Path A Protocol and the CI
  fake-coverage check
status: To Do
assignee: []
created_date: '2026-09-16 13:58'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.1
references:
  - decisions/cloud-portability.md
  - decisions/dependency-injection.md
  - app/bin/check_vendor_package_contract.py
  - app/infrastructure/idempotency/factory.py
parent_task_id: TASK-27
priority: medium
ordinal: 221000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-27 (see the coordinator plan). Closes the decisions/cloud-portability.md contract-4 gaps that are not the storage query redesign itself. Blocks nothing; run it after TASK-27.1 so the storage fake already honours the new spec.

SCOPE
- infrastructure/directory/: no shared in-memory DirectoryProvider exists; the Access Sync suite hand-rolls one inline. Add InMemoryDirectoryProvider inside the package and repoint the hand-rolled doubles at it.
- infrastructure/audit/: add an in-memory AuditTrailService fake. It rides StorageService, so it is unblocked only once TASK-27.1 has landed.
- Wire the CI fake-coverage check named in decisions/cloud-portability.md Checks: every Path A backing-service package under app/infrastructure/<service>/ contains a fake implementation exercised by tests, and the build fails on a Path A Protocol with no fake. The check reads the PACKAGE tree, not app/tests/. In-process mechanisms with no external vendor (events, logging, plugins) are out of scope and must be excluded explicitly, not by accident.
- Follow the existing app/bin guardrail shape (check_deprecated_infra_client_imports.py, check_vendor_package_contract.py): a script under app/bin, a make target, and a listed exclusion set rather than a silent skip.

ALSO IN THIS SLICE. The storage package shape: infrastructure/storage/ still has no factory.py and no settings.py, and get_storage_service sits at the bottom of service.py, unlike directory/, drive/, spreadsheets/ and idempotency/, which all keep the provider in factory.py with a partitioned settings module. Align it here, keeping get_storage_service returning the Protocol type with the concrete class named in exactly one place (decisions/dependency-injection.md).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/directory/ contains an in-memory DirectoryProvider exercised by tests, and the hand-rolled inline doubles in the Access Sync suite are repointed at it
- [ ] #2 infrastructure/audit/ contains an in-memory AuditTrailService fake exercised by tests
- [ ] #3 A CI check fails the build when a Path A package under app/infrastructure/<service>/ defines a Protocol with no in-package fake; it reads the package tree rather than app/tests/, names its excluded in-process mechanisms (events, logging, plugins) explicitly, follows the app/bin guardrail shape and is wired as a make target
- [ ] #4 infrastructure/storage/ matches the Path A package shape: the provider lives in factory.py rather than at the bottom of service.py, a partitioned settings.py exists per decisions/configuration.md, and get_storage_service still returns the Protocol type with the concrete class named in exactly one place
- [ ] #5 Conformance suites pass against fake and real implementations for every Path A Protocol that has one
- [ ] #6 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->
