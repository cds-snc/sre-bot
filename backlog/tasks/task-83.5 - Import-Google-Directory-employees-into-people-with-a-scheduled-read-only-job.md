---
id: TASK-83.5
title: >-
  Import Google Directory users as people with Google identities, using a
  scheduled, read-only job
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:05'
labels:
  - identity
dependencies:
  - TASK-83.4
  - TASK-119
  - TASK-64
references:
  - decisions/people-and-accounts.md
  - app/infrastructure/directory/provider.py
  - decisions/observability.md
parent_task_id: TASK-83
priority: medium
ordinal: 172000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Google is the trusted IdP today (decisions/people-and-accounts.md, Accepted 2026-09-25), so people are created from it. This job creates and refreshes a person for each Google identity, so later steps have people to link accounts to. The same job shape is reused for Entra when Entra becomes a trusted IdP (TASK-83.13).

It reads Google through the directory capability (app/capabilities/directory/api.py, moved by TASK-119) and writes only to the people table. The job is owned by the people capability. It registers through the register_background_jobs hookspec as a Tier-2 job with its schedule and lease TTL in the capability's settings slice, and takes its lease from the coordination contract (decisions/reliability.md).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each active Directory user becomes one person with a google identity keyed by (google, customer id, Directory user id), with idp provenance; the OIDC sub and the email are never used as the key
- [ ] #2 Re-running the job creates no duplicates; a renamed user (changed primaryEmail) keeps the same person and identity, with updated attributes
- [ ] #3 A suspended or deleted Directory user marks its person inactive without deleting it, and a later user given the same email becomes a new person
- [ ] #4 The job makes no writes to Google, runs behind a setting that defaults to off, and logs counts without personal data
- [ ] #5 The job registers through the register_background_jobs hookspec from app/capabilities/people/ as a Tier-2 job with a lease; its body is idempotent when run twice
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
