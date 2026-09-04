---
id: TASK-77
title: >-
  Review access sync treating a Directory batch failure as a warning and
  proceeding with empty desired state
status: To Do
assignee: []
created_date: '2026-09-03 18:03'
updated_date: '2026-09-04 12:39'
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
- [ ] #5 When a per-rule get_group call fails with a non-NOT_FOUND status (TRANSIENT_ERROR, UNAUTHORIZED, or any other classified failure), build_platform_state_from_effective propagates that failure instead of silently excluding the entitlement; a NOT_FOUND result continues to be treated as legitimate absence (skip only that one entitlement), each branch covered by its own test
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEARCH SUMMARY (grounded, current code — TASK-25.1.6.3.1 is Done and already merged, so this plan cites the current provider code, not the retired vendor dispatcher)

AC#1 verdict: NO GUARD EXISTS. The batch failure is destructive, confirmed end-to-end:
- packages/access/sync/desired_state.py:160-175 (build_platform_state_from_effective) — on get_group_members_batch failure, logs a warning and falls through, returning OperationResult.success with desired_members_by_entitlement={}.
- packages/access/sync/application.py:237-239 (sync_platform) — DOES correctly abort when `not desired_result.is_success`. This is the only existing guard, and it never fires for this bug because desired_state.py masks the failure as success.
- packages/access/sync/adapters/aws_identity_center.py:908-923 (_build_canonical_platform_state) — unconditionally seeds `desired_members_by_entitlement = {canonical_id: set() for canonical_id in canonical_id_by_slug.values()}` for EVERY canonical entitlement derived from policy rules, THEN overlays the incoming desired_state data. A swallowed batch failure is indistinguishable from a legitimately-empty result at this point.
- aws_identity_center.py:1094-1096 (_build_current_platform_state call) — `managed_entitlement_ids=set(canonical_desired.desired_members_by_entitlement.keys())` is populated from policy rules regardless of batch success, so CURRENT members ARE fetched for every managed entitlement even when desired is empty.
- policies.py:293-320 (PlatformReconciliationPlanner.plan_platform_actions) — for every entitlement_id, `members_to_remove = current_members - desired_members`; when desired_members is empty, members_to_remove == ALL current_members. Every user in every managed AWS group is planned for `remove_entitlement`.
- Non-dry-run path executes this plan via `_execute_planned_actions` (aws_identity_center.py ~1130-1140). Confirmed destructive, not theoretical: a single transient Directory error empties every managed group platform-wide.

AC#4 verdict (human-confirmed 2026-09-04): FIX IT. The per-rule `get_group` loop at desired_state.py:150-156 conflates a true NOT_FOUND (legitimate — group deleted/renamed) with any other failure status (TRANSIENT_ERROR, UNAUTHORIZED, or any other classified failure) by checking only `is_success`. classify_google_error (integrations/google_workspace/client.py:126-147) already distinguishes these; `get_group`'s OperationResult carries `.status` correctly classified. Only NOT_FOUND is safe to silently skip; anything else must propagate, mirroring the batch fix (AC#5, added to this task).

CONSIDERED AND REJECTED: adopting DirectoryProvider.list_groups_with_members's partial-tolerant `failures` composition (added by TASK-25.1.6.3.1) inside desired_state.py, instead of propagating. Rejected because get_group_members_batch's all-or-nothing contract is an explicit, separate human decision (TASK-25.1.6.3.1's scope note c) that this task must not silently relitigate — AC#2's own wording ("propagate the failure rather than swallow it") already picks the minimal, safe fix. Moving to the partial-tolerant composition would be a materially larger behavioural change (silently proceeding on partial data) than this bug-fix task's scope; if wanted later, it is its own decision with its own review, not a byproduct of this fix.

RELATED FINDING OUT OF SCOPE — filed as TASK-78: a third, separate code path (`discover_group_slugs`, called from `application.py:112`'s `_resolve`, on `list_groups` failure) silently returns an empty group-slug set BEFORE `build_platform_state_from_effective` ever runs, reaching the identical destructive blast radius through effective-policy resolution rather than through either call site this task's ACs cite. Not fixed here — it needs a signature change reviewed for both `sync_user` and `sync_platform` callers, a wider blast radius than this task's contained change.

IMPLEMENTATION STEPS (single PR; touches only app/packages/access/sync/desired_state.py production code + its test double/tests — one subsystem, small diff, no decomposition needed)

STEP 1 — desired_state.py:160-175, propagate the batch failure [AC#2, AC#3]
Replace:
    if not batch_result.is_success:
        log.warning("build_desired_state_batch_members_failed", error=batch_result.message)
    else:
        for group_email, members in (batch_result.data or {}).items():
            ...
with an early return on failure (mirroring the existing authn_members_result pattern at line ~134) and de-indent the population loop to run unconditionally on success:
    if not batch_result.is_success:
        return OperationResult.error(
            batch_result.status,
            message=batch_result.message,
            error_code=batch_result.error_code,
            retry_after=batch_result.retry_after,
        )
    for group_email, members in (batch_result.data or {}).items():
        matched_rule = email_to_rule.get(group_email)
        if matched_rule is None:
            continue
        desired_members_by_entitlement.setdefault(matched_rule.entitlement_id, set()).update(
            member.email.lower() for member in members if member.email.lower() in desired_users
        )
No changes needed in application.py or aws_identity_center.py — application.py's existing `if not desired_result.is_success: return desired_result` (line 237) already aborts correctly once this returns an error.

STEP 2 — desired_state.py:150-156, distinguish NOT_FOUND from other failures [AC#4, AC#5]
Replace:
    for rule in effective.sync_managed_rules():
        group_result = self._directory.get_group(rule.group_slug)
        if not group_result.is_success or not group_result.data:
            log.warning("build_desired_state_group_not_found", group_slug=rule.group_slug)
            continue
        email_to_rule[group_result.data.group_email] = rule
with:
    for rule in effective.sync_managed_rules():
        group_result = self._directory.get_group(rule.group_slug)
        if not group_result.is_success:
            if group_result.status != OperationStatus.NOT_FOUND:
                return OperationResult.error(
                    group_result.status,
                    message=group_result.message,
                    error_code=group_result.error_code,
                    retry_after=group_result.retry_after,
                )
            log.warning("build_desired_state_group_not_found", group_slug=rule.group_slug)
            continue
        if not group_result.data:
            log.warning("build_desired_state_group_not_found", group_slug=rule.group_slug)
            continue
        email_to_rule[group_result.data.group_email] = rule
(OperationStatus is already imported in this file.) The success-but-no-data branch is preserved unchanged (existing edge-case behaviour, not part of this task's finding).

STEP 3 — update docstrings [housekeeping, not a separate AC]
Update `build_platform_state_from_effective`'s one-line docstring to state the propagate-on-failure contract explicitly, and correct `discover_group_slugs`'s docstring is NOT touched (out of scope — that non-fatal design is TASK-78's subject, not this task's).

STEP 4 — test infrastructure: app/tests/integration/packages/access/sync/conftest.py's FakeDirectory [enables AC#3, AC#5 tests]
FakeDirectory currently always returns OperationResult.success for get_group and get_group_members_batch — there is no way to inject a failure today, and build_platform_state_from_effective has ZERO existing test coverage (happy or unhappy path). Extend the constructor with two optional injectable failure overrides, defaulting to current always-succeed behaviour so every existing test is unaffected:
    def __init__(self, ..., batch_members_result: OperationResult | None = None, group_result_by_slug: dict[str, OperationResult] | None = None) -> None:
- `get_group_members_batch` returns `self._batch_members_result` when set, else current behaviour.
- `get_group(slug)` returns `self._group_result_by_slug[slug]` when the slug is a key, else current behaviour (always success).

STEP 5 — tests in app/tests/integration/packages/access/sync/test_desired_state.py [AC#3, AC#5]
Add a new section for `build_platform_state_from_effective` (none exists today):
- test_should_build_platform_state_happy_path: baseline regression proving the untouched success path still works after Step 1/2's restructuring (no existing test covers this method at all).
- test_should_propagate_error_when_batch_members_fetch_fails: FakeDirectory with `batch_members_result=OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="rate limited", error_code="429", retry_after=30)`; assert `not result.is_success`, `result.status == OperationStatus.TRANSIENT_ERROR`, `result.retry_after == 30`, and that no success-with-empty-membership result is produced.
- test_should_skip_entitlement_when_group_not_found: FakeDirectory with one rule's group_result_by_slug entry = `OperationResult.error(OperationStatus.NOT_FOUND, ...)`; assert the build still succeeds, that entitlement is absent from desired_members_by_entitlement, other entitlements are unaffected (documents the still-legitimate NOT_FOUND skip).
- test_should_propagate_error_when_group_lookup_transiently_fails: FakeDirectory with one rule's group_result_by_slug entry = `OperationResult.error(OperationStatus.TRANSIENT_ERROR, ...)`; assert the WHOLE build_platform_state_from_effective call fails with that status (does not silently exclude just that entitlement).

VALIDATION
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run ruff check . && uv run pytest tests --ignore=tests/smoke
Plus: `git diff --name-only` → expect only app/packages/access/sync/desired_state.py, app/tests/integration/packages/access/sync/conftest.py, app/tests/integration/packages/access/sync/test_desired_state.py.
Plus: run the full app/tests/unit/packages/access/sync/** and app/tests/integration/packages/access/sync/** suites explicitly and confirm all pre-existing tests remain green unmodified (proves Step 1/2 are pure restructuring for the success path).

AC TRACEABILITY
AC#1 (destructive-consumer determination) → recorded above, citing aws_identity_center.py:908-923, 1094-1096, policies.py:293-320, application.py:237-239 — no test required, evidentiary record only.
AC#2 (propagate batch failure) → Step 1 → test_should_propagate_error_when_batch_members_fetch_fails.
AC#3 (test proves no mistakable empty-success) → Step 5 → test_should_propagate_error_when_batch_members_fetch_fails.
AC#4 (evaluate group-not-found separately) → recorded above (human-confirmed: fix it) → Step 2.
AC#5 (NOT_FOUND vs other-failure branches) → Step 2 → test_should_skip_entitlement_when_group_not_found + test_should_propagate_error_when_group_lookup_transiently_fails.

ASSUMPTIONS / OPEN QUESTIONS FOR REVIEWER
1. Confirmed with the human during planning (2026-09-04): AC#4 is fixed (NOT_FOUND vs other-status branching), not left as a documented no-op. Recorded as AC#5.
2. TASK-78 was filed to carry the discover_group_slugs finding (a third, separate path to the same destructive shape) since it is out of this task's cited scope and needs its own signature-change review — not blocking this task.
3. This task's fix intentionally does NOT adopt list_groups_with_members's partial-tolerant `failures` composition — see "considered and rejected" above. Flagging in case the reviewer expected that mechanism to be used instead.
4. batch_result.retry_after propagation is new (the sibling authn_members_result early-return at desired_state.py:~134 does not propagate retry_after) — a minor, targeted improvement scoped to the code this task touches, not a blanket fix of that sibling line.

BLAST RADIUS / ROLLBACK
Blast radius: single method's failure-handling in `packages/access/sync/desired_state.py`, consumed only by `AccessSyncApplicationService.sync_platform`. No schema, API, or adapter changes. Behaviourally, IDP outages during platform sync now correctly abort the sync run (surfacing as a sync_platform error, already logged/dispatched via SYNC_FAILED-equivalent handling in application.py) instead of silently reconciling against an empty desired state. Rollback is a straight revert of the one file + its tests; no data migration or dual-write concerns.
<!-- SECTION:PLAN:END -->

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
