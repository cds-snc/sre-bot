---
id: TASK-76
title: >-
  Relocate managed-group policy out of infrastructure/directory into
  packages/access
status: To Do
assignee: []
created_date: '2026-09-03 18:02'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/layers.md
  - decisions/feature-packages.md
  - decisions/configuration.md
  - app/infrastructure/directory/google.py
  - app/infrastructure/configuration/infrastructure/directory.py
  - app/packages/access/catalog/service.py
  - app/packages/access/sync/desired_state.py
priority: medium
ordinal: 145000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-03 (task-planner, human-directed) while planning TASK-25.1.6.3. NOT part of the Google vendor-mirror retirement - it is a layering correction that that work exposed.

THE PROBLEM. app/infrastructure/directory/google.py::GoogleDirectoryProvider embeds access-feature policy inside a shared infrastructure capability:
- _extract_managed_group_email (google.py:158-172) prefers aliases starting with DIRECTORY_MANAGED_GROUP_PREFIX when resolving a group's canonical email.
- _managed_group_query_prefix (google.py:174-193) inspects the caller's query and, when it looks like a managed-prefix search, silently switches strategy from a server-side query to a full unfiltered list plus a client-side alias filter.
- _matches_managed_group_prefix (google.py:195-201) implements that client-side filter.
- _build_directory_group (google.py:269-311) enforces DIRECTORY_MANAGED_GROUP_DOMAIN, returning DIRECTORY_GROUP_DOMAIN_MISMATCH for any group outside it, and gates on DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL.
- The three settings backing all of this live in infrastructure/configuration/infrastructure/directory.py:59-72.

The sole beneficiary is packages/access, which is the only consumer that has managed sg-* security groups: packages/access/catalog/service.py:144 and packages/access/sync/desired_state.py:199 both call list_groups(query=prefix). Human direction (2026-09-03): 'any method in an infrastructure service should be generic; if some business feature specific logic is required afterwards, they probably should own that logic.' This also matches decisions/layers.md - a portable capability's Protocol is capability-shaped and vendor-neutral - and decisions/configuration.md's preference for partitioned, package-owned settings over infrastructure aggregators.

WHY IT IS NOT DONE IN TASK-25.1.6.3. That slice needed a generic list-all path immediately, so it takes the cheap, contained step: split the mapper into a generic _build_group and a managed _build_managed_group, leaving the managed variant in place and byte-for-byte identical. That confines its diff to app/infrastructure/directory/** and keeps packages/access untouched. Completing the relocation touches packages/access, the DirectorySettings partition and their tests - a second subsystem and a behaviour-bearing move, which the implementation-planning size gate keeps out of that PR.

SCOPE. Move the managed-group prefix/domain/alias policy and its settings into packages/access (its own settings partition per decisions/settings-singleton and the packages-python instructions), leaving GoogleDirectoryProvider generic. Decide explicitly whether packages/access filters generic list_groups results itself or supplies the policy to the provider as an injected strategy - do not simply move the branching one layer up without deciding.

PRECONDITION: TASK-25.1.6.3 must have landed the _build_group / _build_managed_group split first, since it is the seam this task extracts along.

NOT IN SCOPE: any Google vendor-mirror work; changing the DirectoryProvider Protocol's method set.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleDirectoryProvider contains no managed-group prefix, alias-preference or managed-domain logic; grep for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix and _extract_managed_group_email returns zero hits under app/infrastructure/
- [ ] #2 DIRECTORY_MANAGED_GROUP_PREFIX, DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL no longer live in DirectorySettings; the policy is owned by packages/access through its own settings partition
- [ ] #3 The chosen mechanism - feature-side filtering of generic results, or an injected policy strategy - is stated in the task notes with its rationale, rather than the branching simply moving up one layer
- [ ] #4 packages/access/catalog and packages/access/sync retain their current observable behaviour, proven by their existing test suites passing with only the seam relocated
- [ ] #5 A group outside the managed domain is returned unchanged by the generic provider and rejected (or ignored) by the feature, with a test at the feature boundary rather than the infrastructure one
<!-- AC:END -->
