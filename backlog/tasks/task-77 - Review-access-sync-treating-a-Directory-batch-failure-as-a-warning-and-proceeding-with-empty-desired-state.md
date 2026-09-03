---
id: TASK-77
title: >-
  Review access sync treating a Directory batch failure as a warning and
  proceeding with empty desired state
status: To Do
assignee: []
created_date: '2026-09-03 18:03'
updated_date: '2026-09-03 20:09'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 20:09
---
TWO OF YOUR PREMISES MOVE WHEN TASK-25.1.6.3.1 MERGES (task-planner, 2026-09-03, human-approved while planning it). Re-read this before you plan; your description currently cites integrations/google_workspace/client.py:193-199 as the source of the all-or-nothing behaviour, and that code will be dead.

1. THE SOURCE OF TRUTH MOVES. execute_batch_request's blanket 'PERMANENT_ERROR for the WHOLE batch as soon as ONE group's request fails' will no longer live in the vendor package. The orchestration moves into GoogleDirectoryProvider (app/infrastructure/directory/google.py), because decisions/outbound-clients.md makes the adapter the classification boundary. Cite the provider, not client.py.

2. THE STATUS BECOMES CLASSIFIED, WHICH SHARPENS YOUR EXPOSURE ARGUMENT RATHER THAN WEAKENING IT. The batch failure will be classified by classify_google_error, so a 429 or 503 on ONE group now yields TRANSIENT_ERROR (with retry_after when Google supplies it) for the whole batch, not PERMANENT_ERROR. packages/access/sync/desired_state.py:163 only reads is_success, so its behaviour is bit-for-bit unchanged - it still logs build_desired_state_batch_members_failed and proceeds with an empty desired state. But you now have a typed, correct signal available at that call site to branch on, which is exactly what a fix needs.

3. STILL TRUE AND UNCHANGED: get_group_members_batch remains ALL-OR-NOTHING by explicit human decision. TASK-25.1.6.3.1 deliberately does not change its return contract, so one bad group key can still empty the desired state for every entitlement in the batch. Your AC#3 stands as written.

4. NEW OPTION AVAILABLE TO YOU. TASK-25.1.6.3.1 also adds a per-group-failure-tolerant surface on the same provider - list_groups_with_members returns success carrying a failures tuple of DirectoryGroupFailure(group_email, status, error_code, message) alongside the groups that succeeded. If your fix wants 'proceed with the groups that worked, and never silently present a partial result as complete', the mechanism now exists in infrastructure and you would not be inventing it. Whether desired_state should move onto it, or get_group_members_batch should gain the same shape, is your call - do not assume either.

5. UNRELATED DEFECT ALSO CLOSED BY .3.1, worth knowing since it touches the same call: get_group_members_batch ignores nextPageToken today and silently truncates any group past the first member page. Fixed there. It can only ever return MORE members, so it does not interact with your failure-handling scope.
---
<!-- COMMENTS:END -->
