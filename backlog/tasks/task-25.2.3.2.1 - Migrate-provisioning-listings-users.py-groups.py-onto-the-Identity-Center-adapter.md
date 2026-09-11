---
id: TASK-25.2.3.2.1
title: >-
  Migrate provisioning listings (users.py, groups.py) onto the Identity Center
  adapter
status: To Do
assignee: []
created_date: '2026-09-11 20:55'
updated_date: '2026-09-11 20:57'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.1
references:
  - app/modules/provisioning/users.py
  - app/modules/provisioning/groups.py
  - app/packages/aws_platform/adapters/identity_center.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 194000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate). Migrates modules/provisioning/users.py:58 (list_users) and modules/provisioning/groups.py:142-144 (list_groups_with_memberships) off integrations.aws.identity_store onto build_identity_center_adapter(). Human decision carried over: bulk listings that fail raise the module-local DirectoryUsersUnavailableError / DirectoryGroupsUnavailableError (already defined in these files for the Google branches at users.py:12-18/44-51 and groups.py:12-18/111-117) instead of crashing with TypeError -- mirror those branches exactly for the aws_identity_center case. No other caller is touched in this slice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/provisioning/users.py no longer imports integrations.aws.identity_store; get_users_from_integration's aws_identity_center branch calls build_identity_center_adapter().list_users() and raises DirectoryUsersUnavailableError(message, error_code) on a non-success result, mirroring the google_directory branch
- [ ] #2 modules/provisioning/groups.py no longer imports integrations.aws.identity_store; get_groups_from_integration's aws_identity_center branch calls build_identity_center_adapter().list_groups_with_memberships() and raises DirectoryGroupsUnavailableError(message, error_code) on a non-success result, mirroring the google_groups branch
- [ ] #3 tests/unit/modules/provisioning/test_provisioning_users.py and tests/modules/provisioning/test_provisioning_groups.py are retargeted to patch build_identity_center_adapter instead of identity_store, with a new failure-path test asserting the correct exception type per module
- [ ] #4 ruff, mypy (no new errors) and pytest pass with output recorded; a grep of these two files shows zero references to integrations.aws.identity_store
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (re-read in full 2026-09-11: modules/provisioning/users.py (71 lines), modules/provisioning/groups.py (227 lines), packages/aws_platform/adapters/identity_center.py (306 lines, list_users at line 156, list_groups_with_memberships at line 217), tests/unit/modules/provisioning/test_provisioning_users.py (120 lines), tests/modules/provisioning/test_provisioning_groups.py (lines 320-429 read directly), and the legacy integrations/aws/identity_store.py list_users (line 138) and list_groups_with_memberships (line 285) for shape comparison.)

## Data-shape finding (top risk check, resolved: NO mismatch)
- `identity_store.list_users()` (legacy, line 138-144) calls `execute_aws_api_call(..., paginated=True, keys=["Users"])` and returns the raw, unprojected `Users` page items (dicts with `UserId`, `UserName`, `Emails`, `Name`, etc.).
- `IdentityCenterAdapter.list_users()` (adapter, line 156-159) calls `self._paginate("list_users", "Users", ...)`, which flattens every page's `Users` key into the identical raw dict list (adapter.py lines 84-98). `OperationResult.data` on success is that same list — byte-for-byte shape parity with the legacy return.
- `identity_store.list_groups_with_memberships()` (legacy, line 285-368) projects each group to exactly `{"GroupId", "DisplayName", "Description", "IdentityStoreId"}` (line 322-324) then attaches `group["GroupMemberships"] = memberships` where each membership's `MemberId` dict is `.update()`-d with the matching user record (line 361-367).
- `IdentityCenterAdapter.list_groups_with_memberships()` (adapter, line 217-293) does the identical projection (`_GROUP_PROJECTION_KEYS = ("GroupId", "DisplayName", "Description", "IdentityStoreId")`, line 30, applied at line 247) and the identical `membership["MemberId"].update(member_details)` enrichment (line 286), returning `OperationResult.success(data=groups_with_memberships, ...)`.
- Conclusion: `result.data` for both listings is exactly the raw/projected dict shape `modules/provisioning/users.py` and `groups.py`'s downstream consumers (`filters.compare_lists` on `"UserName"`, `log_groups` on `"DisplayName"`/`"GroupMemberships"`/`"MemberId.UserName"`, `identity_center.py`'s `sync_users`/`sync_groups`) already depend on. No adapter-shape shim is needed in this slice — only the success/failure branching around the call changes.

## Ordered Steps

### Step 1 — modules/provisioning/users.py
File: app/modules/provisioning/users.py
- Replace `from integrations.aws import identity_store` (line 6) with `from packages.aws_platform.adapters.identity_center import build_identity_center_adapter` (verify exact import path per Assumption 1 below before writing).
- Replace line 58 `users = identity_store.list_users()` with:
  ```
  result = build_identity_center_adapter().list_users()
  if not result.is_success:
      log.error("list_users_failed", error_code=result.error_code, error=result.message)
      raise DirectoryUsersUnavailableError(result.message, result.error_code)
  users = result.data or []
  ```
  placed inside the existing `case "aws_identity_center":` branch (lines 53-58), reusing the `log` already bound at line 31 and the `DirectoryUsersUnavailableError` class already defined in this file (lines 12-18) — mirrors the `google_directory` branch's error handling at lines 45-51 exactly.
- No other change to this file; `get_users_from_integration`'s signature, the `case _:` fallthrough, and the trailing `processing_filters` loop (lines 62-67) are untouched.

### Step 2 — modules/provisioning/groups.py
File: app/modules/provisioning/groups.py
- Replace `from integrations.aws import identity_store` (line 5) with the same adapter import as Step 1.
- Replace lines 142-144:
  ```
  groups = identity_store.list_groups_with_memberships(
      groups_filters=pre_processing_filters,
  )
  ```
  with:
  ```
  result = build_identity_center_adapter().list_groups_with_memberships(groups_filters=pre_processing_filters)
  if not result.is_success:
      log.error("list_groups_with_memberships_failed", error_code=result.error_code, error=result.message)
      raise DirectoryGroupsUnavailableError(result.message, result.error_code)
  groups = result.data or []
  ```
  inside the existing `case "aws_identity_center":` branch (lines 137-148), reusing the `log` bound at line 90 and the `DirectoryGroupsUnavailableError` class already defined in this file (lines 12-18) — mirrors the `google_groups` branch's error handling at lines 111-117 exactly.
- `integration_name`, `group_display_key`, `members`, `members_display_key` assignments at lines 145-148 are unchanged (they describe the same projected-group shape the adapter still returns, per the data-shape finding above).

### Step 3 — Retarget tests/unit/modules/provisioning/test_provisioning_users.py
- `test_should_return_raw_identity_store_dicts_from_the_aws_branch` (line 103-107): replace `monkeypatch.setattr(users.identity_store, "list_users", lambda *args, **kwargs: aws_users)` with a fake adapter injected via `monkeypatch.setattr(users, "build_identity_center_adapter", lambda: fake_adapter)` where `fake_adapter.list_users.return_value = OperationResult.success(data=aws_users)`; assertion (`== aws_users`) is unchanged since the shape is identical (per the data-shape finding).
- `test_should_raise_when_aws_identity_store_list_users_returns_false` (line 109-116): replace with a case where the fake adapter's `list_users()` returns `OperationResult.error(status=OperationStatus.TRANSIENT_ERROR, message="...", error_code="...")`; assert `pytest.raises(users.DirectoryUsersUnavailableError)` and that `excinfo.value.error_code` matches, mirroring `test_should_raise_a_module_local_error_carrying_the_error_code_on_a_failed_listing` (line 84-91) for the google branch.
- Both cases can reuse the existing `FakeDirectory`-style pattern already in this file (lines 18-27) generalized to a minimal `FakeIdentityCenterAdapter` with a `list_users` method, or a plain `mocker.Mock(spec=IdentityCenterAdapter)` per the testing-standards Protocol-fake convention — prefer the latter since `IdentityCenterAdapter` is a concrete class, not a Protocol, so `mocker.Mock(spec=IdentityCenterAdapter)` gives the same call-signature safety.
- No other test in this file references `identity_store`; leave untouched.

### Step 4 — Retarget tests/modules/provisioning/test_provisioning_groups.py (legacy tree, minimal edit only)
This file lives outside `app/tests/unit` in the legacy `tests/modules/` tree. Per the testing-standards skill ("legacy directories... make the minimal edit that keeps it passing; do not opportunistically migrate it"), it stays exactly where it is — this slice retargets its patches only, it does not move the file or rewrite it to the new-style layout.
- `test_get_groups_from_integration_case_aws` (line 333-348), `test_get_groups_from_integration_filters_applied` (line 380-409), `test_get_groups_from_integration_filters_returns_subset` (line 412+), and `test_get_groups_from_integration_case_invalid` (line 366-377): replace `@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")` with `@patch("modules.provisioning.groups.build_identity_center_adapter")`, configuring `mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.success(data=aws_groups)`; update the `assert_called_once_with(groups_filters=[])` assertions to assert on `mock_build.return_value.list_groups_with_memberships`.
- `test_get_groups_from_integration_case_aws_raises_when_integration_returns_false` (line 351-363, the TASK-25.2.1 characterization pin): replace the `False`-return characterization with `mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.error(status=OperationStatus.TRANSIENT_ERROR, message="...", error_code="...")`; replace `pytest.raises(TypeError)` with `pytest.raises(groups.DirectoryGroupsUnavailableError)`, asserting the message/error_code round-trip — this is the new-contract replacement AC#2 in the parent task called for.
- Add one new case (not previously characterized, since AC#1 of TASK-25.2.1 found groups.py's False-path untested): `test_get_groups_from_integration_case_aws_empty_listing_returns_empty_list`, asserting `OperationResult.success(data=[])` yields `response == []` without raising — the empty-listing boundary case.

## AC Traceability
- AC#1 (users.py migrated, DirectoryUsersUnavailableError on non-success) → Step 1 → tests: `test_should_return_raw_identity_store_dicts_from_the_aws_branch` (happy path), `test_should_raise_when_aws_identity_store_list_users_returns_false` (renamed/rewritten to assert the new exception, not TypeError).
- AC#2 (groups.py migrated, DirectoryGroupsUnavailableError on non-success) → Step 2 → tests: `test_get_groups_from_integration_case_aws` (happy path), `test_get_groups_from_integration_case_aws_raises_when_integration_returns_false` (rewritten).
- AC#3 (both test files retargeted with new failure-path tests) → Steps 3 and 4 → the specific renamed/added tests listed above.
- AC#4 (gates pass, zero identity_store references in these two files) → Step 5 (verification) below.

## Test Matrix
- app/tests/unit/modules/provisioning/test_provisioning_users.py (EXTEND/REWRITE, 2 cases touched): happy path (adapter success, raw dict list passed through unchanged); non-success path (any OperationStatus other than SUCCESS) raises `DirectoryUsersUnavailableError` carrying `message`/`error_code`.
- app/tests/modules/provisioning/test_provisioning_groups.py (EXTEND/REWRITE, legacy tree, left in place per testing-standards; 4 cases touched + 1 new): happy path with groups+memberships (existing `aws_groups_w_users` fixture data unchanged), empty-listing success (`data=[]` → `response == []`, new case closing the AC#1-of-25.2.1 gap), non-success path raises `DirectoryGroupsUnavailableError`, filters-applied happy paths (post-processing filter application unaffected by the call-site change).
- Boundary case explicitly covered: an empty (but successful) listing must NOT raise — only `not result.is_success` raises; this distinguishes "zero users/groups" (valid, e.g. a fresh AWS org) from "listing failed" (must raise), a distinction the old TypeError-crash characterization conflated.

## Assumptions and How to Verify
1. Assumes the adapter's import path is `packages.aws_platform.adapters.identity_center.build_identity_center_adapter` — verify with `rg -n "^from packages" app/tests/unit/packages/aws_platform/test_aws_platform_identity_center_provider.py` immediately before writing the import (this is the same open assumption carried from the parent task's plan).
2. Assumes `OperationResult`/`OperationStatus` construction helpers used in tests (`OperationResult.success(data=...)`, `OperationResult.error(status=..., message=..., error_code=...)`) match `infrastructure/operations/result.py`'s actual factory signatures — verify by reading that module once before writing the fakes (the parent task's grounding already located it; re-confirm the exact keyword names, e.g. whether it's `data=` or a positional-only first arg, per the existing google-branch tests in test_provisioning_users.py lines 39-44, which already use this exact pattern successfully).
3. Assumes no other caller in this repo calls `modules.provisioning.users.get_users_from_integration("aws_identity_center")` or the groups equivalent with an expectation of the *legacy* `False`-swallow contract (i.e., no caller wraps these in a try/except expecting `False` back) — verify with `rg -n "get_users_from_integration\(.aws_identity_center" app --glob '!tests/**'` and the groups equivalent; the only known caller is `modules/aws/identity_center.py`'s `synchronize()` via `groups.get_groups_from_integration("aws_identity_center", ...)`, which is migrated separately in TASK-25.2.3.2.2 and does not call `users.get_users_from_integration("aws_identity_center")` at all (it calls `identity_store.list_users()` directly, out of scope for this slice).
4. Assumes `mocker.Mock(spec=IdentityCenterAdapter)` is an acceptable double style here even though the surrounding legacy-groups test file uses `@patch` module-level mocking — testing-standards' "mirror the subject module's existing house style" guidance (carried from TASK-25.2.1's STUB STRATEGY note) argues for keeping `@patch("modules.provisioning.groups.build_identity_center_adapter")` in the legacy file (Step 4) for consistency, while the newer `test_provisioning_users.py` may use either; if in doubt at implementation time, default to `monkeypatch.setattr` / `@patch` on the factory function to match each file's existing pattern rather than introducing `mocker.Mock(spec=...)` cold.

## Blast Radius and Rollback
- Blast radius: only the `aws_identity_center` listing paths of `get_users_from_integration` and `get_groups_from_integration`. Callers: `modules/aws/identity_center.py`'s `synchronize()` (via `groups.get_groups_from_integration`) and `modules/aws/aws.py`'s `provision_aws_users` (via `users.get_users_from_integration`, called only for the `"delete"` branch at line 338) — both are downstream of this slice but not modified by it; TASK-25.2.3.2.2 migrates `identity_center.py`'s own direct `identity_store.list_users()` calls separately.
- A regression here surfaces as either a spurious `DirectoryUsersUnavailableError`/`DirectoryGroupsUnavailableError` on a healthy AWS Identity Center (over-eager raise) or a silent swallow reverting to the old crash-on-empty-false behavior (under-eager raise) — both are caught by the boundary test matrix above (empty-success must not raise; any non-success must raise).
- A single `git revert` of this slice's PR fully restores prior behavior: it only touches these two call sites and their tests, with no schema/data migration and no other file depending on the new exception-raising behavior yet (TASK-25.2.3.2.2, .3, .4 are not yet merged when this slice ships first, per the proposed dependency order).
- No ordering constraint beyond depending on TASK-25.2.3.1 (the adapter), which is already Done.

## Size-Gate Arithmetic (passes)
- Production files touched: 2 (modules/provisioning/users.py, modules/provisioning/groups.py).
- Estimated production LOC changed: ~10 in users.py (import swap + 5-line branch replacement) + ~12 in groups.py (import swap + 6-line branch replacement) ≈ 22 LOC.
- Subsystems crossed: 1 (provisioning module, single package).
- No mix of mechanical refactor and behavior change at different call sites — both files get the identical treatment (adapter call + typed-exception raise), which is itself the one behavior change this slice makes, applied uniformly.
- Verdict: well under the ~400 LOC / ~10 file / two-subsystem thresholds; independently shippable and revertible without the other three slices existing.

## Verification (Step 5)
Run from app/: `uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run pytest tests --ignore=tests/smoke`, and `rg -n "integrations\.aws\.identity_store|integrations import identity_store" app/modules/provisioning/users.py app/modules/provisioning/groups.py` (expect zero hits). Record all four outputs in this task's notes at finalization.
<!-- SECTION:PLAN:END -->
