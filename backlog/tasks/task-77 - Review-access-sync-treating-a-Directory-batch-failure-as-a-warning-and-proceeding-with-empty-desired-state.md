---
id: TASK-77
title: >-
  Review access sync treating a Directory batch failure as a warning and
  proceeding with empty desired state
status: To Do
assignee: []
created_date: '2026-09-03 18:03'
labels:
  - reliability
dependencies: []
references:
  - decisions/operation-result.md
  - decisions/reliability.md
  - app/packages/access/sync/desired_state.py
  - app/infrastructure/directory/google.py
priority: high
type: bug
ordinal: 146000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-03 (task-planner, human-directed) while planning TASK-25.1.6.3. Pre-existing; unrelated to the Google vendor-mirror retirement. Filed as a review rather than a fix because the correct behaviour is a product/safety decision, not a refactor.

THE CONCERN. app/packages/access/sync/desired_state.py:160-175 builds the desired membership state:

    batch_result = self._directory.get_group_members_batch(list(email_to_rule.keys()), include_member_types={'USER'})
    if not batch_result.is_success:
        log.warning('build_desired_state_batch_members_failed', error=batch_result.message)
    else:
        ...populate desired_members_by_entitlement...

On failure it logs a warning and FALLS THROUGH, returning OperationResult.success with desired_members_by_entitlement left empty. A caller cannot distinguish 'these entitlements legitimately have no members' from 'we could not reach the IDP'. If any downstream reconciliation removes memberships not present in the desired state, a single transient IDP error would present as 'remove everything'.

WHY THE EXPOSURE IS REAL RATHER THAN THEORETICAL. get_group_members_batch is all-or-nothing: integrations/google_workspace/client.py:193-199 returns a PERMANENT_ERROR for the WHOLE batch as soon as ONE group's request fails, discarding the results that did succeed. So one bad group key is enough to empty the desired state for every entitlement in the batch. classify_google_error also maps rate-limit and 5xx responses into results, so this is reachable from ordinary transient conditions, not only from misconfiguration.

WHAT THIS TASK MUST DETERMINE FIRST, before changing anything: whether any consumer of DesiredPlatformState actually acts destructively on an empty desired_members_by_entitlement, or whether a guard elsewhere already prevents it. Read the sync coordinator and its reconciliation step end to end. If a guard exists, close this task by recording where it is and adding a regression test that pins it. If no guard exists, the fix is to propagate the failure rather than swallow it - the same warning-and-continue shape also appears at desired_state.py:150-156 for a missing group, which is a different and probably legitimate case, so do not blanket-change both.

INTERACTION WITH THE 25.1.6 WORK: TASK-25.1.6.3.1 fixes a separate defect in the same call - get_group_members_batch ignores nextPageToken and silently truncates groups past the first page - but deliberately does NOT change its return contract, so this behaviour is unaffected by it and remains live either way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 It is determined and recorded in the task notes whether any consumer of DesiredPlatformState acts destructively on an empty desired_members_by_entitlement, citing the exact reconciliation call sites read
- [ ] #2 If an existing guard prevents destructive action, a regression test pins it and this task closes with that evidence; if no guard exists, the IDP failure is propagated rather than swallowed at desired_state.py:163
- [ ] #3 A test proves that a failing get_group_members_batch does not result in a desired state that a caller could mistake for 'no members'
- [ ] #4 The distinct warning-and-continue at desired_state.py:150-156 (group not found for a rule) is evaluated separately and either left intentionally unchanged with a recorded rationale, or fixed on its own merits
<!-- AC:END -->
