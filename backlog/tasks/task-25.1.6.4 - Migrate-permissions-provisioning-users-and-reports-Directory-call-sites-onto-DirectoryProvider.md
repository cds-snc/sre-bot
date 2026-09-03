---
id: TASK-25.1.6.4
title: >-
  Migrate permissions, provisioning-users and reports Directory call sites onto
  DirectoryProvider
status: To Do
assignee: []
created_date: '2026-09-02 15:00'
updated_date: '2026-09-03 18:02'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-02 17:16
---
PRE-REGISTERED BY TASK-25.1.6.1 PLANNING (2026-09-02, task-planner). Your AC#6 says "TASK-25.1.6.1 characterization tests for modules/reports/google_groups.py pass unchanged, or every intentional behaviour change is named in the task notes". Here is what you will actually be looking at.

FILE: app/tests/unit/modules/reports/test_google_groups_report.py (NOT app/tests/modules/... -- TASK-25.1.6.1 AC#1 was corrected to the unit tree per decisions/testing.md).

STRUCTURE: three classes, deliberately split by lifetime.
- TestGenerateGroupMembersReportBehaviour -- respond strings, the AWS- name exclusion, sheet-name truncation, values matrix, control flow. These MUST keep passing after your migration; if one goes red, you changed observable behaviour.
- TestGenerateGroupMembersReportBoundary -- the arguments handed to google_directory.list_groups()/list_group_members(). These are EXPECTED to be translated by you, not deleted: the seam moves from patch("modules.reports.google_groups.google_directory") to a DirectoryProvider double obtained via get_directory_provider(). Translating them is normal; silently dropping them is not.
- TestGenerateGroupMembersReportFailureModes -- includes two cases that are directly your problem: (a) list_groups raising propagates uncaught today and create_file has ALREADY run, so a failed Directory call leaves an empty spreadsheet behind; (b) list_group_members raising on the second group propagates with ZERO sheet writes done. Under OperationResult these exceptions no longer cross the boundary, so both of these tests WILL need rewriting -- that rewrite is your AC#4 error-branch handling, and the notes must name it.

ALSO INHERITED: the tests monkeypatch modules.reports.google_groups.FOLDER_REPORTS_GOOGLE_GROUPS because GOOGLE_RESOURCES is not in the pytest env block, and they patch time.sleep (the module sleeps 1.1s per group). Keep both when you rework them.
---

author: @task-planner
created: 2026-09-03 18:02
---
API SHAPE AND FIELD INVENTORY PRE-REGISTERED BY TASK-25.1.6.3 PLANNING (2026-09-03, task-planner). TASK-25.1.6.3 was split; you depend only on Slice A (TASK-25.1.6.3 itself), which is unblocked for you as soon as it merges. The new TASK-25.1.6.3.1 is Slice B and gates TASK-25.1.6.5, not you.

WHAT SLICE A HANDS YOU.
- list_users(query: str = '', limit: int | None = None). limit=None (the NEW DEFAULT) means every user in the domain. Your AC#2 is therefore satisfied by calling list_users() with no arguments - there is no magic number to pass. Related defect fixed in the same slice: today's limit is a post-hoc slice applied AFTER walking every page (google.py:402 then :418), so list_users(limit=3) currently pulls the whole directory; after Slice A the pagination stops early.
- list_groups(query: str = '', limit: int | None = None). An EMPTY query means every group in the domain, mapped by a new generic mapper that does NOT apply managed-alias preference or managed-domain enforcement. modules/reports/google_groups.py:69 calls list_groups() with no arguments today, so this is the direct replacement. Do not pass a wildcard.
- DirectoryUser gains given_name and family_name.
- Unmappable group entries are logged at warning and counted rather than dropped silently; result contents are unchanged.

FIELD MAPPING FOR YOUR THREE FILES (AC#5). modules/permissions/handler.py reads user['email'] at :20 and :36 -> DirectoryMember.email. modules/provisioning/users.py:26 returns raw user dicts consumed downstream as primaryEmail / name.givenName / name.familyName by modules/aws/identity_center.py:145-149 and :316-321 -> DirectoryUser.email / .given_name / .family_name. modules/reports/google_groups.py reads group['name'] at :70 and :87, group['email'] at :83, member['email'] and member['role'] at :117 -> DirectoryGroup.name / .group_email and DirectoryMember.email / .role.

FIELDS THAT DO NOT SURVIVE, decided in Slice A rather than left for you: group directMembersCount and member status are NOT carried on the dataclasses (grep-confirmed zero downstream reads). DirectoryMember.provider_user_id is hardcoded None (google.py:257) - the Google member id is mapped to membership_id instead - so do not read provider_user_id expecting a value.

ONE THING TO WATCH THAT IS YOURS, NOT SLICE A'S: modules/provisioning/users.py:36 applies utils.filters.filter_by_condition to the returned users, and modules/aws/identity_center.py:137 compares on the 'primaryEmail' dict key. Those helpers operate on dict keys, not dataclass attributes. Repointing users.py is therefore not a pure swap - decide explicitly whether the filter contract moves to attribute access or the consumer adapts, and cover it with a test.
---
<!-- COMMENTS:END -->
