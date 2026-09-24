---
id: TASK-83.4
title: >-
  Create the app/capabilities/people/ capability (domain, store, in-memory fake,
  api.py, hookspecs) with no consumers
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-24 20:08'
labels:
  - identity
dependencies:
  - TASK-83.1
  - TASK-83.2
  - TASK-83.3
  - TASK-108
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-122
references:
  - decisions/people-and-accounts.md
  - decisions/plugins.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-83
priority: medium
ordinal: 171000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24: decisions/capability-packages.md was deleted. decisions/people-and-accounts.md and plugin-architecture.md now fix the home: app/capabilities/people/. Its public surface is api.py (the Protocol, Person and Account types, provider function) plus its own hookspecs module; everything else is private. It persists through the storage contract resolved from the service registry and never imports infrastructure/. It is declared by an entry point with an enablement key. Generate it with the package generator (TASK-114).

The first capability package under decisions/plugin-architecture.md. It owns the identity model from decisions/people-and-accounts.md:
- Person, with an app-generated id;
- Account, identified by (system, tenant, account_id), with id aliases;
- Link, with provenance (directory, admin, verified, hr_id);
- Kind (employee, contractor);
- homes per service kind.

Nothing consumes it yet, so it can merge without changing behavior. The package location is app/capabilities/people/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/people/ exposes api.py with its Protocol, frozen domain types and provider function, plus a hookspecs module; nothing else is imported from outside the package, and its README states the classification
- [ ] #2 Linking an account already claimed by another person fails with a conflict and changes nothing
- [ ] #3 Links can only be created or removed with a provenance value, and every creation or removal emits an audit event through capabilities/audit/api.py
- [ ] #4 No lookup, key or join uses an email, UPN or display name, as covered by tests
- [ ] #5 An in-memory fake passes the same contract tests as the storage-backed store
- [ ] #6 The capability is declared by an entry point with an enablement key, registers at startup without import-time side effects, persists only through the storage contract from the registry, and no feature imports it yet
- [ ] #7 Full test suite, ruff, mypy and lint-imports pass
<!-- AC:END -->
