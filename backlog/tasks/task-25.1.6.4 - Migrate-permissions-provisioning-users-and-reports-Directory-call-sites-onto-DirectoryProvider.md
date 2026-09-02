---
id: TASK-25.1.6.4
title: >-
  Migrate permissions, provisioning-users and reports Directory call sites onto
  DirectoryProvider
status: To Do
assignee: []
created_date: '2026-09-02 15:00'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/outbound-clients.md
  - decisions/dependency-injection.md
  - app/infrastructure/directory/provider.py
  - app/modules/permissions/handler.py
  - app/modules/provisioning/users.py
  - app/modules/reports/google_groups.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 135000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second Directory slice. The decision is settled (see TASK-25.1.6.3): DirectoryProvider survives, google_directory.py dies, the legacy consumers move onto the Protocol.

This slice moves the three consumers whose calls map onto EXISTING Protocol methods, leaving the harder groups-with-members consumer and the module deletion to TASK-25.1.6.5.

CALL SITES (grep-confirmed 2026-09-02, six sites across four files; three files here):
- app/modules/permissions/handler.py:15 and :32 - google_directory.list_group_members(group_key) -> DirectoryProvider.get_group_members(group_key).
- app/modules/provisioning/users.py:26 - google_directory.list_users() -> the unbounded list-users capability added by TASK-25.1.6.3. This is a FULL-DIRECTORY sync; do not let it silently truncate.
- app/modules/reports/google_groups.py:47 - google_directory.list_groups() -> the unbounded list-groups capability added by TASK-25.1.6.3; and :61 - google_directory.list_group_members(group["email"]) -> get_group_members. This file also has Sheets and Drive call sites; those belong to other TASK-25.1.6 children and are OUT OF SCOPE here.

HOW THE PROVIDER IS OBTAINED: via infrastructure/directory/factory.py::get_directory_provider(), per decisions/dependency-injection.md and the project's provider-singleton rules - these modules must not construct GoogleDirectoryProvider themselves and must not import integrations/google_workspace at all when this slice lands.

REAL WORK, NOT A REPOINT: the legacy functions return raw list[dict] with Google field names (primaryEmail, email, role, type); the Protocol returns DirectoryUser/DirectoryGroup/DirectoryMember frozen dataclasses wrapped in OperationResult. Each consumer therefore needs (a) field mapping onto the dataclass attributes, and (b) an explicit decision for the error branch, since exceptions no longer cross the boundary - OperationResult.is_success must be handled rather than ignored. modules/reports/google_groups.py's blanket try/except around its Sheets call is NOT the model to copy for the Directory calls.

GUARDED BY: TASK-25.1.6.1's characterization tests, which must be in place for modules/reports/google_groups.py before this slice touches it (that file has no test file today).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/permissions/handler.py resolves DirectoryProvider via get_directory_provider() and uses get_group_members at both call sites; it no longer imports integrations.google_workspace
- [ ] #2 modules/provisioning/users.py uses the unbounded list-users capability and a test proves it receives more users than the old default limit would have allowed (no silent truncation of the directory sync)
- [ ] #3 modules/reports/google_groups.py's two Directory call sites use DirectoryProvider; its Sheets and Drive call sites are untouched by this task
- [ ] #4 Every migrated call site handles the OperationResult error branch explicitly - no bare is_success ignore, no blanket except Exception around a Directory call - and each error branch has a test
- [ ] #5 Google-shaped raw dicts no longer reach these three modules: they consume DirectoryUser/DirectoryGroup/DirectoryMember attributes, with field mappings verified against TASK-25.1.6.3's recorded field inventory
- [ ] #6 TASK-25.1.6.1's characterization tests for modules/reports/google_groups.py pass unchanged, or every intentional behaviour change is named in the task notes
- [ ] #7 integrations/google_workspace/google_directory.py still exists after this task (TASK-25.1.6.5 deletes it) but has exactly one remaining production consumer: modules/provisioning/groups.py
<!-- AC:END -->
