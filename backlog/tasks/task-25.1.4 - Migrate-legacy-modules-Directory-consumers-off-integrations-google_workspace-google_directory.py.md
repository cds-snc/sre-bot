---
id: TASK-25.1.4
title: >-
  Migrate legacy modules/ Directory consumers off
  integrations/google_workspace/google_directory.py
status: To Do
assignee: []
created_date: '2026-07-31 18:33'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/integrations/google_workspace/google_directory.py
parent_task_id: TASK-25.1
priority: high
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.1. A SEPARATE consumer path from TASK-22.4 (which only covers the infrastructure/directory/{factory,google}.py Provider abstraction): modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py, modules/reports/google_groups.py import integrations/google_workspace/google_directory.py DIRECTLY, bypassing the Provider entirely, and route through the same execute_google_api_call dispatcher. Reuse (do not reinvent) the AdminDirectoryResource factory + classify_google_error TASK-22.4 already builds for the Directory surface - this slice is consumer migration only, not a second Directory client. Flag as an open doubt for implementation-time review: whether these 4 modules should instead be migrated onto the infrastructure/directory Provider/DirectoryService Protocol (reusing TASK-22.4's abstraction) rather than the raw factory-built Resource directly, given they are cross-cutting legacy modules/ consumers, not a single feature adapter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py, and modules/reports/google_groups.py no longer import integrations.google_workspace.google_directory's execute_google_api_call-backed calls; each is wired onto TASK-22.4's factory + classify_google_error (or the DirectoryService Protocol, whichever is decided at implementation time)
- [ ] #2 All 4 consumers behave identically for their Directory-related calls (existing tests pass, behavior-neutral)
- [ ] #3 integrations/google_workspace/google_directory.py (the non-facade, non-_next original) has zero remaining production consumers once this slice lands, or is itself migrated onto the same factory+classify pattern if a shared implementation is chosen
<!-- AC:END -->
