---
id: TASK-84
title: >-
  Collapse get_group_members' inline member mapping onto
  GoogleDirectoryProvider's shared helpers
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
ordinal: 182000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pure refactor inside app/infrastructure/directory/google.py; no behaviour change.

FOUND while planning TASK-25.1.6.3.1 and deliberately left out of TASK-25.1.6.11: it is not vendor-SDK isolation, and folding it into a deletion PR would mix a refactor with other work (implementation-planning size gate, rule #3). Human-decided 2026-09-10 to track it standalone at low priority.

CURRENT STATE (verified on main 2026-09-10): get_group_members (:503-562) re-implements, inline, the member-type normalization (:537-547) and the type-filter + _build_directory_member loop (:549-560). The same logic already exists as _normalize_member_types (:167) and _map_members (:181), used by get_group_members_batch (:587, :600) and list_groups_with_members (:857, :878). Three call sites, two implementations.

CHECK BEFORE COLLAPSING: the inline copy returns permanent_error with message 'include_member_types must contain at least one type' and error_code DIRECTORY_MEMBER_TYPES_INVALID for an empty-after-strip set. Confirm _normalize_member_types produces the identical OperationResult (status, message, error_code), and that the inline loop's isinstance(item, dict) skip and empty-type pass-through match _map_members, before replacing it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 get_group_members delegates member-type normalization to _normalize_member_types and mapping to _map_members; no inline copy of either remains
- [ ] #2 Existing get_group_members tests pass unchanged, including the invalid include_member_types error (same status, message and error_code) and the non-dict item skip
- [ ] #3 No OAuth scope, request parameter or pagination change in get_group_members
<!-- AC:END -->
