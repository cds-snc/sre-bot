---
id: TASK-132
title: Report IdP group members added outside the requestable-groups catalogue
status: To Do
assignee: []
created_date: '2026-09-25 19:43'
updated_date: '2026-09-25 19:58'
labels:
  - security
  - identity
  - access
milestone: m-4
dependencies:
  - TASK-61
references:
  - decisions/authorization.md
priority: low
ordinal: 280000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/authorization.md: a scheduled comparison of IdP memberships against the git-reviewed catalogue and the bot's grant records. It reports members added directly in the IdP, and privileged members whose grant has expired in the bot but who are still listed in the IdP, to the group's owners and SRE. It never removes anyone. The job reads the IdP through the Directory API only, registers through register_background_jobs as a Tier-2 job with a lease, and alerts through the notifications capability (TASK-125).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Members of catalogue groups without a matching approved grant, and privileged members whose grant expired in the bot but who are still listed in the IdP, are reported to the group's owners and SRE
- [ ] #2 The job makes no writes to the IdP, runs behind a setting that defaults to off, and logs counts without personal data
- [ ] #3 The job registers as a Tier-2 job with a lease; its body is idempotent when run twice
- [ ] #4 Full test suite, ruff and mypy pass
<!-- AC:END -->
