---
id: TASK-78
title: >-
  Review access sync discover_group_slugs IDP failure silently emptying
  effective policy before reconciliation
status: To Do
assignee: []
created_date: '2026-09-04 12:38'
labels:
  - reliability
dependencies: []
references:
  - decisions/operation-result.md
  - decisions/reliability.md
  - app/packages/access/sync/desired_state.py
  - app/packages/access/sync/application.py
priority: high
type: bug
ordinal: 147000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-04 (task-planner, human-directed) while planning TASK-77. Same destructive blast radius as TASK-77 (a Directory failure silently producing an empty desired state that a platform-sync reconciler cannot distinguish from a legitimate 'no managed groups' state, which per TASK-77's confirmed finding at packages/access/sync/adapters/aws_identity_center.py's _build_canonical_platform_state + _build_current_platform_state + policies.py PlatformReconciliationPlanner.plan_platform_actions plans removal of every user from every currently-managed group), reached via a THIRD, separate code path that TASK-77's acceptance criteria do not cite and its fix does not cover.

THE PATH. app/packages/access/sync/application.py:112 (AccessSyncApplicationService._resolve, called by both sync_user and sync_platform) calls self._membership_builder.discover_group_slugs(self._config, platform) BEFORE resolve_effective_policy(...). desired_state.py's discover_group_slugs (around line 186) queries self._directory.list_groups(query=prefix); on failure it logs discover_groups_failed and returns an empty set -- by its own docstring, deliberately non-fatal: 'Returns an empty set on IDP failure (non-fatal; the coordinator proceeds with an empty rule set).'

WHY THIS MATTERS. An empty discovered-slugs set flows into resolve_effective_policy(config, platform, discovered=set()), which then has zero sync_managed_rules for that platform. build_platform_state_from_effective (once TASK-77 lands) will see email_to_rule stay empty and skip the batch call entirely -- there is no IDP failure at that point to propagate, because the empty state was manufactured one level up, before build_platform_state_from_effective ever ran. TASK-77's fix (propagate get_group / get_group_members_batch failures) does not and cannot catch this: the failure already happened and was silently absorbed inside discover_group_slugs.

WHAT THIS TASK MUST DETERMINE: whether 'proceed with an empty rule set' on a list_groups outage was a deliberate product decision (e.g. discovery is expected to be best-effort because policy is re-resolved every run and a transient miss is tolerable) or an oversight of the same shape TASK-77 just fixed. If it is the same defect class, the fix likely needs to propagate the list_groups failure out of discover_group_slugs (or out of _resolve) rather than defaulting to set() -- but note _resolve()'s current return contract for discover_group_slugs is a bare set[str], not an OperationResult, so the fix may need a signature change reviewed for both sync_user and sync_platform callers, which is a wider blast radius than TASK-77's contained change and should be scoped/estimated on its own.

Do not assume TASK-77's fix pattern transfers directly -- confirm the actual call contract and both call sites (sync_user single-user path and sync_platform batch path) before proposing a fix shape.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 It is determined and recorded whether discover_group_slugs' empty-set-on-IDP-failure fallback was a deliberate product decision or an oversight, citing the exact reasoning
- [ ] #2 If it is the same defect class as TASK-77, a fix is proposed that propagates the list_groups failure to both sync_user and sync_platform callers without silently emptying effective policy, with the signature change reviewed for both call sites
- [ ] #3 A test proves that a list_groups failure during group discovery does not result in a platform sync that treats the platform as having zero managed groups
<!-- AC:END -->
