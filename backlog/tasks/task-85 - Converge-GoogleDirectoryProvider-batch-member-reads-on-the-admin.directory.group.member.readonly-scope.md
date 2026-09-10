---
id: TASK-85
title: >-
  Converge GoogleDirectoryProvider batch member reads on the
  admin.directory.group.member.readonly scope
status: To Do
assignee: []
created_date: '2026-09-10 17:25'
labels:
  - clients
  - cleanup
milestone: m-3
dependencies: []
references:
  - app/infrastructure/directory/google.py
priority: low
ordinal: 183000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Small OAuth least-privilege change inside app/infrastructure/directory/google.py. This is a behaviour change (the scope requested at token minting), not a no-op, so it ships alone.

FOUND while planning TASK-25.1.6.3.1 and deliberately left out of TASK-25.1.6.11: not vendor-SDK isolation, and a scope change must not ride along with a deletion PR. Human-decided 2026-09-10 to track it standalone at low priority.

CURRENT STATE (verified on main 2026-09-10): the same members.list call is issued under two scopes.
- get_group_members (:520) and list_groups_with_members (:864) request https://www.googleapis.com/auth/admin.directory.group.member.readonly.
- get_group_members_batch (:592) requests the broader https://www.googleapis.com/auth/admin.directory.group.readonly.
Group-level reads (:612, :772, :912) legitimately use group.readonly and are NOT in scope. The domain-wide delegation grant for member.readonly demonstrably exists, since get_group_members uses it in production.

VERIFY WHEN PLANNING: current consumers of get_group_members_batch (grep); that the delegated service account's DWD grant lists member.readonly in every environment, not only production.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 get_group_members_batch requests admin.directory.group.member.readonly, matching get_group_members and list_groups_with_members
- [ ] #2 A unit test asserts the scope passed to the provider's service factory for get_group_members_batch; group-level reads keep admin.directory.group.readonly
- [ ] #3 The implementation notes record that the domain-wide delegation grant covering member.readonly was confirmed for every deployed environment before merge
<!-- AC:END -->
