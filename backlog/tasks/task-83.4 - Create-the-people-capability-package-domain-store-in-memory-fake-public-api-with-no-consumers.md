---
id: TASK-83.4
title: >-
  Create the app/capabilities/people/ capability (domain, store, in-memory fake,
  api.py, hookspecs) with no consumers
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 19:43'
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
decisions/people-and-accounts.md (Accepted 2026-09-25) and plugin-architecture.md fix the home: app/capabilities/people/. Its public surface is api.py (the Protocol, Person, Identity and Account types, and a provider function) plus its own hookspecs module; everything else is private. It persists through the storage contract resolved from the service registry and never imports infrastructure/. It is declared by an entry point with an enablement key. Generate it with the package generator (TASK-114).

It is the first capability package under decisions/plugin-architecture.md. It owns the identity model:
- Person: an opaque, app-generated id, active or inactive, with a primary identity for profile attributes.
- Identity: (idp, tenant, subject). google uses the Directory user id; entra uses oid with tid.
- Account: (platform, tenant, account_id), with id aliases.
- Link: provenance is one of idp, idp_subject, sso_email or admin. A flagged state covers an sso_email link whose evidence diverged.
- Homes per service kind.
There is no person kind and no role or permission field; authorization is TASK-129.

Nothing consumes it yet, so it can merge without changing behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/people/ exposes api.py with its Protocol, frozen Person, Identity and Account types and provider function, plus a hookspecs module; nothing else is imported from outside the package, and its README states the classification
- [ ] #2 Claiming an identity or account already claimed by another person fails with a conflict and changes nothing
- [ ] #3 Links can only be created or removed with a provenance value (idp, idp_subject, sso_email, admin), and every creation or removal emits an audit event through capabilities/audit/api.py
- [ ] #4 No key uses an email, UPN, display name or Google OIDC sub; api.py exports no kind, role or permission field, as covered by tests
- [ ] #5 An in-memory fake passes the same contract tests as the storage-backed store
- [ ] #6 The capability is declared by an entry point with an enablement key, registers at startup without import-time side effects, persists only through the storage contract from the registry, and no feature imports it yet
- [ ] #7 Full test suite, ruff, mypy and lint-imports pass
- [ ] #8 A Person can be a merged_into tombstone that resolves to its survivor; provenance includes verified
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 (people-and-accounts.md amendment): the domain also needs verified link provenance and a merged_into tombstone on Person, so a merged person still resolves to its survivor. The join flow itself is TASK-83.14.
<!-- SECTION:NOTES:END -->
