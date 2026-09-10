---
id: TASK-83.12
title: >-
  Add the Microsoft Graph vendor package (client factory, error classification,
  settings) with no consumers
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
  - clients
dependencies:
  - TASK-83.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
parent_task_id: TASK-83
priority: medium
ordinal: 179000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Importing Microsoft accounts needs an outbound client for Microsoft Graph that follows decisions/outbound-clients.md and decisions/sdk-typing.md. No Graph client exists in app/integrations/ today.

Teams identifies users by their Entra object id, so the same client later serves Teams-related account work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/integrations/ gains a Microsoft Graph package that exports only a client factory, a classify function and settings
- [ ] #2 The factory sets explicit timeouts and SDK-native retry, following the non-idempotent write rule in decisions/outbound-clients.md
- [ ] #3 Classification tests map each expected Graph error family to a status and let unexpected exceptions propagate
- [ ] #4 The required Entra application permissions are documented and limited to reading users
- [ ] #5 Full test suite, ruff, mypy and app/bin/check_sdk_typing.py pass
<!-- AC:END -->
