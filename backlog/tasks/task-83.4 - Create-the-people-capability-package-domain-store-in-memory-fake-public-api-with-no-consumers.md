---
id: TASK-83.4
title: >-
  Create the people capability package (domain, store, in-memory fake, public
  api) with no consumers
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.1
  - TASK-83.2
  - TASK-83.3
references:
  - decisions/people-and-accounts.md
  - decisions/capability-packages.md
  - decisions/plugins.md
parent_task_id: TASK-83
priority: medium
ordinal: 171000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The first capability package under decisions/capability-packages.md (Draft). It owns the identity model from decisions/people-and-accounts.md:
- Person, with an app-generated id;
- Account, identified by (system, tenant, account_id), with id aliases;
- Link, with provenance (directory, admin, verified, hr_id);
- Kind (employee, contractor);
- homes per service kind.

Nothing consumes it yet, so it can merge without changing behavior. The package location follows capability-packages.md; the umbrella name is still undecided.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The package exposes api.py with its Protocol, frozen domain types and provider function; nothing else is imported from outside the package
- [ ] #2 Linking an account already claimed by another person fails with a conflict and changes nothing
- [ ] #3 Links can only be created or removed with a provenance value, and every creation or removal emits an audit event
- [ ] #4 No lookup, key or join uses an email, UPN or display name, as covered by tests
- [ ] #5 An in-memory fake passes the same contract tests as the DynamoDB-backed store
- [ ] #6 The package registers at startup through plugins without import-time side effects, and no feature imports it yet
- [ ] #7 Full test suite, ruff and mypy pass
<!-- AC:END -->
