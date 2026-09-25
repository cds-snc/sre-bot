---
id: TASK-83.13
title: >-
  Import Microsoft Entra users as people with Entra identities once Entra is a
  trusted IdP
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:06'
labels:
  - identity
dependencies:
  - TASK-83.4
  - TASK-83.7
  - TASK-83.12
references:
  - decisions/people-and-accounts.md
parent_task_id: TASK-83
priority: medium
ordinal: 180000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build this when Entra is configured as a trusted IdP, alongside Google or instead of it. Until then it doesn't start (decisions/people-and-accounts.md, Accepted 2026-09-25).

It uses the same job shape as TASK-83.5. Each Entra user becomes a person with an identity keyed by (entra, tid, oid), with idp provenance. UPN and mail are attributes only; the pairwise sub is never used. A human who already has a Google identity starts as a second person, and a shared email only suggests a join in the TASK-83.7 flow. Teams accounts later link exactly through aadObjectId, which equals oid (idp_subject provenance).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each Entra user in a configured trusted tenant becomes one person with an identity keyed by tid and oid, with idp provenance; UPN, mail and sub are never keys
- [ ] #2 Re-running creates no duplicates, and a renamed user keeps the same person and identity with updated attributes
- [ ] #3 A disabled or deleted Entra user marks its person inactive without deleting it
- [ ] #4 An Entra user sharing an email with a Google identity produces a suggested join in the TASK-83.7 flow, never a merged person
- [ ] #5 The job runs behind a setting that defaults to off and makes no writes to Entra
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
