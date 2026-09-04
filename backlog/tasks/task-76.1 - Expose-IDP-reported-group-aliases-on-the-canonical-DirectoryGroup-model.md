---
id: TASK-76.1
title: Expose IDP-reported group aliases on the canonical DirectoryGroup model
status: To Do
assignee: []
created_date: '2026-09-04 14:17'
labels:
  - layering
milestone: m-3
dependencies: []
parent_task_id: TASK-76
priority: medium
ordinal: 148000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-76 (see the coordinator plan, decision D1). Infrastructure-only, purely additive, no behaviour change.

WHY. packages/access cannot own managed-group policy while the only alias information the IDP returns is consumed and discarded inside GoogleDirectoryProvider. _extract_managed_group_email (app/infrastructure/directory/google.py:269-285) picks a canonical email by preferring an alias with the managed prefix, and _matches_managed_group_prefix (google.py:306-313) filters on aliases - both read _extract_group_aliases (google.py:~255-266) and neither surfaces the aliases to the caller. DirectoryGroup (app/infrastructure/directory/models.py) has no aliases field, so a feature-side policy is impossible to write without this slice.

FACT vs POLICY. The aliases a directory reports for a group are a vendor-neutral FACT about the group, in the same class as name and description, and belong on the canonical model. Which alias is canonical, which prefix is managed and which domain is authoritative are POLICY and are NOT part of this slice - they stay where they are until TASK-76.3 cuts over and TASK-76.4 deletes them.

SCOPE.
- Add aliases: tuple[str, ...] = () to the frozen DirectoryGroup dataclass. Tuple, not list, to keep the dataclass hashable and immutable per the type-model boundary rules.
- Populate it in BOTH _build_group (google.py:420-451) and _build_managed_group (google.py:453-493), reusing the existing _extract_group_aliases helper. Normalization must match what the existing alias logic assumes (stripped, lowercased) so TASK-76.2's policy sees the same values the provider does today.
- Add the missing provider mapping unit tests (per TASK-76 plan fact F4 there are none today).

NOT IN SCOPE. Any change to DirectoryProvider's method set; any removal or relocation of managed-group policy or settings; any change in packages/access.

TESTING (decisions/testing.md). Unit tests over recorded Google group payload dicts at the mapper seam: a group with aliases populates them in order; a group with no aliases yields an empty tuple; existing group fields are unchanged. No network, no moto needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DirectoryGroup carries aliases as an immutable tuple field defaulting to empty, and remains a frozen dataclass
- [ ] #2 Both _build_group and _build_managed_group populate aliases from the provider payload using the existing extraction helper, with identical normalization to the current alias logic
- [ ] #3 Unit tests at the mapper seam cover a group with aliases, a group without aliases, and confirm no other DirectoryGroup field changed
- [ ] #4 No managed-group policy or setting is added, removed or relocated by this slice, and no file under app/packages/ is modified
- [ ] #5 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->
