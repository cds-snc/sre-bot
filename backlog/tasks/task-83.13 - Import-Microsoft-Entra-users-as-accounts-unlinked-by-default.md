---
id: TASK-83.13
title: 'Import Microsoft Entra users as accounts, unlinked by default'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
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
Some employees work only from their Microsoft identity, and their Microsoft addresses differ from their Google ones. Entra accounts must exist in the people table so SRE can link them through the same review flow.

Accounts are keyed by (microsoft, tenant id, object id). UPN and mail are attributes only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each Entra user in the configured tenant becomes one account keyed by tenant id and object id, with UPN and mail as attributes
- [ ] #2 The import creates no links, and re-running it creates no duplicates
- [ ] #3 A renamed user keeps the same account, with updated attributes
- [ ] #4 The job runs behind a setting that defaults to off and makes no writes to Entra
- [ ] #5 Suggested links for Entra accounts appear in the SRE review flow
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
