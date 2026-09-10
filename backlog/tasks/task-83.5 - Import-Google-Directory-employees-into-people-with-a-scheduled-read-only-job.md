---
id: TASK-83.5
title: 'Import Google Directory employees into people with a scheduled, read-only job'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.4
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
For now, Google Directory is the authoritative source of employees (decisions/people-and-accounts.md). This job creates and refreshes employee persons and their Google accounts, so later steps have people to link to.

It reads Google through the existing infrastructure/directory provider (tolerated; no new infrastructure service) and writes only to the people table.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each active Directory user becomes one person with a google account, keyed by the Directory user id, with directory provenance
- [ ] #2 Re-running the job creates no duplicates; a renamed user (changed primaryEmail) keeps the same person and account, with updated attributes
- [ ] #3 Suspended or deleted Directory users are marked as such, not deleted
- [ ] #4 Kind is read from the source attribute decided in the acceptance task, never derived from an address
- [ ] #5 The job makes no writes to Google, runs behind a setting that defaults to off, and logs counts without personal data
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
