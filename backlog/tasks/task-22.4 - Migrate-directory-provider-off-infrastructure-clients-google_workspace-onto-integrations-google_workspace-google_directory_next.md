---
id: TASK-22.4
title: >-
  Migrate directory provider off infrastructure/clients/google_workspace onto
  integrations/google_workspace/google_directory_next
status: To Do
assignee: []
created_date: '2026-07-29 21:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.3
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/infrastructure/directory/factory.py
  - app/infrastructure/directory/google.py
  - app/integrations/google_workspace/google_directory_next.py
parent_task_id: TASK-22
priority: high
ordinal: 107000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-22 (parent). Repoint the Google Workspace directory consumers off the deprecated GoogleWorkspaceClients facade onto integrations/google_workspace/google_directory_next.

Call sites: infrastructure/directory/factory.py:6 (GoogleWorkspaceClients, get_google_workspace_clients) and infrastructure/directory/google.py:7 (GoogleWorkspaceClients). GoogleDirectoryProvider calls self._directory.<method> at 11 sites (google.py lines 287-705): health_check, get_user, list_users, list_members, get_batch_group_members, get_group, add_member, remove_member, has_member, list_groups, list_user_groups. google_directory_next.py covers most as MODULE-LEVEL OperationResult functions. VERIFY GAP: confirm a health_check equivalent exists in google_directory_next/google_service_next; if absent, add a minimal OperationResult health_check there (behavior-parity with the deprecated one) as part of this slice. Rework factory.py so GoogleDirectoryProvider no longer receives a GoogleWorkspaceClients facade. Preserve all OperationResult outcomes and payload normalization exactly. Wire to _next as-is (no rename = TASK-23; no raise/classify = TASK-25).

Test migration: relocate app/tests/integrations/google_workspace/test_google_directory_next.py and test_google_service_next.py to app/tests/unit/integrations/google_workspace/; keep directory provider tests in tests/unit/infrastructure/directory/, updating mock target paths. Legacy tests/integrations/ count must drop.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/directory/factory.py and google.py no longer import infrastructure.clients.google_workspace; GoogleDirectoryProvider is backed by integrations/google_workspace/google_directory_next
- [ ] #2 A health_check equivalent returning OperationResult exists in integrations/google_workspace and is used by GoogleDirectoryProvider with behavior parity
- [ ] #3 All tests/unit/infrastructure/directory/ tests pass behavior-neutral; google_directory_next + google_service_next tests relocated to tests/unit/integrations/google_workspace/ (legacy tests/integrations/ file count reduced)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral: directory provider outcomes identical; PR references decisions/layers.md and decisions/outbound-clients.md
<!-- DOD:END -->
