---
id: TASK-78
title: >-
  Review access sync discover_group_slugs IDP failure silently emptying
  effective policy before reconciliation
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-04 12:38'
updated_date: '2026-09-04 13:37'
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
- [x] #1 It is determined and recorded whether discover_group_slugs' empty-set-on-IDP-failure fallback was a deliberate product decision or an oversight, citing the exact reasoning
- [x] #2 If it is the same defect class as TASK-77, a fix is proposed that propagates the list_groups failure to both sync_user and sync_platform callers without silently emptying effective policy, with the signature change reviewed for both call sites
- [x] #3 A test proves that a list_groups failure during group discovery does not result in a platform sync that treats the platform as having zero managed groups
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEARCH SUMMARY (grounded, current code)

CONFIRMED CALL CONTRACT. Only one call site exists: application.py:112, AccessSyncApplicationService._resolve(), called identically by both sync_user() and sync_platform() via the shared (adapter, effective, error) tuple contract. discover_group_slugs() currently returns a bare set[str] and swallows list_groups() failures internally (desired_state.py ~186-207), violating DirectoryMembershipBuilder's own class docstring, which states "All public methods return OperationResult so callers can handle IDP failures through the standard result contract without catching exceptions." It is the only public method on this class that does not.

AC#1 VERDICT (human-confirmed 2026-09-04): OVERSIGHT, same defect class as TASK-77. Evidence: (1) list_groups (infrastructure/directory/google.py:865-) already distinguishes a genuine IDP failure from a legitimate zero-match query -- a zero-match query returns OperationResult.success(data=[]), and is_success is False only for a classified error via classify_google_error. So the empty-set fallback in discover_group_slugs conflates "outage" with "this platform legitimately declares zero groups", which is exactly the ambiguity operation-result.md's envelope exists to prevent. (2) The class's own docstring contract (above) is violated only by this method. (3) TASK-77 already fixed the identical swallow-on-failure shape one level down in the same file/class.

BLAST-RADIUS CORRECTION (human-confirmed 2026-09-04): TASK-78's filed description claims "same destructive blast radius as TASK-77 -- plans removal of every user from every currently-managed group." Tracing the actual downstream effect through PolicyEngine.plan_actions (policies.py:209-278) and the AWS adapter shows this is NOT accurate. When discover_group_slugs silently returns an empty set, resolve_effective_policy() produces an EMPTY entitlement_rules list (not just empty membership data, unlike TASK-77's bug, which left rules populated and only emptied membership data). plan_actions' removal branch only fires for an entitlement id that IS in sync_managed_by_id (built from those same, now-empty, rules) -- `if ent_id in sync_managed_by_id and ent_id not in desired_ids`. With sync_managed_by_id empty, NO removals are planned for any currently-held entitlement, in either sync_user or sync_platform (aws_identity_center.py: canonical_id_by_slug is built from context.entitlement_rules, also empty, so managed_entitlement_ids is empty and _build_current_platform_state skips list_members_for_groups entirely).

ACTUAL EFFECT: entitlement grant/revoke enforcement for the platform is silently SKIPPED ENTIRELY for the duration of the outage -- stale access persists (a user who should lose a group membership does not), and new access is not granted -- while authn-driven user lifecycle (provision/disable/delete) is UNAFFECTED because it does not depend on discovered rules. This is a real defect (an outage is indistinguishable from "zero declared groups", silently disabling drift correction for as long as list_groups keeps failing) but it is silent non-enforcement, not active destructive removal. Recorded here to correct the task's filed premise before implementation; does not change the required fix.

FIX SHAPE: single choke point. Both callers already funnel through _resolve(); no changes needed in sync_user() or sync_platform() themselves.

IMPLEMENTATION STEPS (single PR; two production files + three test files, one subsystem, no decomposition needed)

STEP 1 -- desired_state.py: discover_group_slugs propagates failure [AC#2]
Change return type from `set[str]` to `OperationResult[set[str]]`. On `list_result.is_success` False: return `OperationResult.error(list_result.status, message=list_result.message, error_code=list_result.error_code, retry_after=list_result.retry_after)` (keep the existing discover_groups_failed warning log for operator visibility). On success: wrap the existing discovered-set computation in `OperationResult.success(data=discovered)`. Update the method's docstring to state the propagate-on-failure contract (replacing "non-fatal ... proceeds with an empty rule set"), and update the module docstring's one-line mention of discover_group_slugs to match.

STEP 2 -- application.py: _resolve() handles the new return type [AC#2, AC#3]
Replace:
    discovered = self._membership_builder.discover_group_slugs(self._config, platform)
    effective = resolve_effective_policy(self._config, platform, discovered)
    return adapter, effective, None
with:
    discovered_result = self._membership_builder.discover_group_slugs(self._config, platform)
    if not discovered_result.is_success:
        return None, None, discovered_result
    effective = resolve_effective_policy(self._config, platform, discovered_result.data or set())
    return adapter, effective, None
No changes needed to sync_user() or sync_platform(): both already do `if error is not None: return error` immediately after calling _resolve().

STEP 3 -- test infrastructure: two FakeDirectory doubles gain injectable list_groups failure [enables AC#3]
- app/tests/integration/packages/access/sync/conftest.py FakeDirectory: add `list_groups_result: OperationResult | None = None` constructor param; `list_groups()` returns it when set, else current behaviour (mirrors the batch_members_result/group_result_by_slug injection pattern TASK-77 added).
- app/tests/unit/packages/access/sync/test_application.py FakeDirectory: same addition; also add a `list_groups_result` passthrough parameter to the `make_coordinator()` factory, defaulting to None so every existing test is unaffected.

STEP 4 -- new tests, section C in app/tests/integration/packages/access/sync/test_desired_state.py [AC#3]
- test_should_discover_matching_group_slugs: happy-path regression (none exists today) -- matching slugs returned, non-matching filtered, result.is_success, result.data is the expected set.
- test_should_propagate_error_when_group_discovery_fails: FakeDirectory with `list_groups_result=OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="rate limited", error_code="429", retry_after=30)`; assert not is_success, status/error_code/retry_after match, data is None.
Add C1/C2 entries to the module docstring's "Scenarios covered" list, matching the existing A/B lettering convention.

STEP 5 -- new tests, section F-06 in app/tests/unit/packages/access/sync/test_application.py [AC#3]
- test_sync_user_propagates_error_when_group_discovery_fails: make_coordinator(list_groups_result=OperationResult.error(TRANSIENT_ERROR, ...)); assert coordinator.sync_user(...) is not success, status/error_code match, and adapter.calls is empty (reconcile_user never invoked).
- test_sync_platform_propagates_error_when_group_discovery_fails: same shape for sync_platform(...), asserting adapter.calls is empty (reconcile_platform never invoked).
These are the tests that directly prove AC#3: a platform/user sync no longer proceeds as if the platform had zero managed groups when discovery fails.

VALIDATION
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run ruff check . && uv run pytest tests --ignore=tests/smoke
Plus: `git diff --name-only` -> expect only app/packages/access/sync/desired_state.py, app/packages/access/sync/application.py, app/tests/integration/packages/access/sync/conftest.py, app/tests/integration/packages/access/sync/test_desired_state.py, app/tests/unit/packages/access/sync/test_application.py.
Plus: run app/tests/unit/packages/access/sync/** and app/tests/integration/packages/access/sync/** explicitly and confirm all pre-existing tests remain green unmodified (proves Steps 1/2 are additive, not restructuring).

AC TRACEABILITY
AC#1 (determine deliberate vs oversight) -> recorded above (human-confirmed): oversight, same defect class as TASK-77 -- no test required, evidentiary record only. Blast-radius correction also recorded (human-confirmed) alongside it.
AC#2 (propagate failure to both callers) -> Steps 1-2 (single choke point at _resolve(), confirmed sufficient for both sync_user and sync_platform).
AC#3 (test proves no zero-managed-groups treatment) -> Steps 4-5 (four new tests: direct discover_group_slugs coverage plus both application-level callers).

ASSUMPTIONS / OPEN QUESTIONS FOR REVIEWER
1. Confirmed with the human during planning (2026-09-04): AC#1 is oversight/fix, not deliberate-design-document-only.
2. Confirmed with the human during planning (2026-09-04): the task's filed blast-radius description ("removal of every user from every currently-managed group") is corrected to "silent skip of entitlement grant/revoke enforcement for the platform" per the PolicyEngine.plan_actions trace above -- this does not change the fix, only the recorded severity mechanism.
3. Fix is scoped to discover_group_slugs + _resolve() only (not sync_user/sync_platform bodies) since both already funnel through the shared tuple contract -- flagged for reviewer awareness since the task's own filing anticipated changes at both call sites.

BLAST RADIUS / ROLLBACK
Blast radius: discover_group_slugs()'s failure handling in packages/access/sync/desired_state.py, and _resolve()'s handling of that result in packages/access/sync/application.py -- consumed only by AccessSyncApplicationService.sync_user() and .sync_platform(). No schema, API, or adapter changes. Behaviourally, an IDP outage during group discovery now correctly aborts sync_user/sync_platform (surfacing as an error result, already logged/dispatched via existing error-handling paths) instead of silently proceeding with an effective policy that has zero entitlement rules for that platform. Rollback is a straight revert of the two production files + their tests; no data migration or dual-write concerns.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED (2026-09-04).

AC#1 verdict: OVERSIGHT, same defect class as TASK-77. DirectoryMembershipBuilder's own class docstring states all public methods return OperationResult; discover_group_slugs was the sole violator. list_groups already distinguishes a zero-match query (success with data=[]) from a classified failure, so the empty-set fallback conflated 'IDP outage' with 'platform declares zero groups' -- exactly the ambiguity decisions/operation-result.md exists to prevent. Blast-radius correction from the plan stands: actual effect was silent SKIP of entitlement grant/revoke enforcement (stale access persists, new access not granted), not active mass removal, because plan_actions' removal branch requires ent_id in sync_managed_by_id which is empty when rules are empty.

AC#2 changes (production, 2 files):
- packages/access/sync/desired_state.py: discover_group_slugs now returns OperationResult[set[str]]; on list_groups failure it keeps the discover_groups_failed warning and returns OperationResult.error propagating status/message/error_code/retry_after; success wraps the discovered set. Method and module docstrings updated to the propagate-on-failure contract.
- packages/access/sync/application.py: _resolve() returns (None, None, discovered_result) when discovery fails, else resolves effective policy from discovered_result.data. No changes needed in sync_user()/sync_platform() -- both already short-circuit on the shared error tuple, confirming the single choke point reviewed for both call sites.

AC#3 test evidence (test scaffolding was already present on the branch):
- tests/integration/packages/access/sync/test_desired_state.py section C: test_should_discover_matching_group_slugs (happy path, prefix filtering) and test_should_propagate_error_when_group_discovery_fails (TRANSIENT_ERROR/429/retry_after=30 propagated, data is None).
- tests/unit/packages/access/sync/test_application.py: sync_user and sync_platform discovery-failure tests assert an error result and that the adapter is never invoked -- proving no sync proceeds as if the platform had zero managed groups.

VALIDATION: mypy on both changed files -> no new errors (only pre-existing integrations/slack/help.py:125). ruff check . -> All checks passed. Targeted access sync suites: 181 passed. Full 'make test' run by the human -> all green.

FOR HUMAN VERIFICATION (DoD): review the behaviour change that an IDP list_groups outage now aborts sync_user/sync_platform with an error result (surfaced through existing error dispatch/logging) instead of silently no-op'ing enforcement; confirm alerting/runbook expectations for that new error path.
<!-- SECTION:NOTES:END -->
