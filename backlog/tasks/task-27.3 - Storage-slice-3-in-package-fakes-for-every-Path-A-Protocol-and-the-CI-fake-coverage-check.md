---
id: TASK-27.3
title: >-
  Storage slice 3: the CI fake-coverage check over hosting contracts and
  capability api.py Protocols
status: To Do
assignee: []
created_date: '2026-09-16 13:58'
updated_date: '2026-09-24 20:09'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.1
  - TASK-106
references:
  - decisions/cloud-portability.md
  - decisions/dependency-injection.md
  - app/bin/check_vendor_package_contract.py
  - app/infrastructure/idempotency/factory.py
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: medium
ordinal: 221000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-27, rescoped 2026-09-24 to decisions/plugin-architecture.md and cloud-portability.md (contract 4). The fake contract covers two kinds of Protocol:
- hosting contracts: Protocols in app/contracts/ implemented in app/infrastructure/ (storage, coordination, queue, secrets);
- capability api.py Protocols that face an external system (directory, drive, spreadsheets, audit, people, approvals).
It does not cover feature Path B adapters or in-process mechanisms (logging, the plugin manager).

What moved out of this slice:
- The shared in-memory DirectoryProvider is built by TASK-119 when directory moves to app/capabilities/directory/, and the audit fake by TASK-122 when audit moves to app/capabilities/audit/. Building them in app/infrastructure/ first would move them twice.
- The former AC to give infrastructure/storage/ a cached factory.py provider is dropped. decisions/dependency-injection.md replaces cached provider functions with the service registry (TASK-109), so that shape would be built and then deleted.

Remaining scope:
- wire the CI fake-coverage check. It fails the build when a Protocol in app/contracts/ that has an app/infrastructure/ implementation, or an externally facing capability api.py Protocol, has no in-memory fake exercised by tests. It reads the package tree, not app/tests/, and names its excluded in-process mechanisms explicitly.
- Follow the app/bin guardrail shape: a script, a make target, a listed exclusion set.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A CI check fails the build when a hosting contract in app/contracts/ or an externally facing capability api.py Protocol has no in-memory fake exercised by tests; it reads the package tree rather than app/tests/, names its excluded in-process mechanisms (logging, plugins) explicitly, follows the app/bin guardrail shape and is wired as a make target
- [ ] #2 The check's exclusion list covers feature Path B adapters by rule, not by listing them one by one
- [ ] #3 Conformance suites pass against fake and real implementations for every covered Protocol that has one
- [ ] #4 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->
