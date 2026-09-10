---
id: TASK-83.7
title: Let SRE create and remove links and review suggested links in bulk
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.5
  - TASK-83.6
references:
  - decisions/people-and-accounts.md
  - decisions/security.md
parent_task_id: TASK-83
priority: medium
ordinal: 174000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Links are never inferred from matching emails or names (decisions/people-and-accounts.md). With hundreds of employees, SRE needs to review suggested links in bulk and confirm them as admin links.

The interface (a Slack command and modal, or an HTTP admin endpoint) is chosen during planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Only SRE-authorized users can create, confirm or remove links
- [ ] #2 Suggestions come from matching attributes and are listed for review; they never create a link on their own
- [ ] #3 Confirming suggestions in bulk creates one admin-provenance link and one audit event per account, recording who confirmed it
- [ ] #4 A link to an account already claimed by another person is rejected and shown to the reviewer
- [ ] #5 Removing a link is audited and leaves the account unlinked
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
