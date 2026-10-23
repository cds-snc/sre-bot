---
id: TASK-25.2.3.2.2
title: Migrate modules/aws/identity_center.py onto the Identity Center adapter
status: Done
assignee:
  - '@me'
created_date: '2026-09-11 20:55'
updated_date: '2026-09-14 13:45'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.1
references:
  - app/modules/aws/identity_center.py
  - app/modules/provisioning/entities.py
  - app/modules/provisioning/users.py
  - app/packages/aws_platform/adapters/identity_center.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 195000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate). Migrates modules/aws/identity_center.py off integrations.aws.identity_store onto build_identity_center_adapter(): the two direct list_users() calls in synchronize() (:70, :79), raising DirectoryUsersUnavailableError (imported from modules.provisioning.users) on a non-success result; and the four create_user/delete_user/create_group_membership/delete_group_membership callables passed to entities.provision_entities at :155/:171/:261/:282/:329/:348. entities.provision_entities itself is unchanged (it tests 'if response:' and an OperationResult is always truthy), so this slice adds small local bridge functions that map the provision_entities entity-dict kwargs to adapter arguments and return result.data on success or False (logged with status and error_code) on any non-success -- preserving the legacy False-swallow contract so failed entities are still recorded as failed and the loop continues. Per the ConflictException human decision on TASK-25.2.3.1: create_user/create_group_membership conflicts now arrive as OperationResult(status=PERMANENT_ERROR) instead of a raised ClientError; the bridges' generic non-success handling already treats this as a failed (not crashing) entity -- document this explicitly at these two call sites.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 synchronize()'s two list_users() call sites use build_identity_center_adapter().list_users() and raise DirectoryUsersUnavailableError on a non-success result
- [x] #2 four local bridge functions (create_user, delete_user, create_group_membership, delete_group_membership) wrap the adapter, map entity-dict kwargs to adapter arguments, and return result.data on success or False (logged with status and error_code) on non-success, including the PERMANENT_ERROR conflict case for create_user and create_group_membership
- [x] #3 all six entities.provision_entities call sites pass the new local bridges instead of identity_store.* -- :155/:171/:261/:282 in sync_users/sync_groups and :329/:348 in provision_aws_users; entities.py itself is unchanged
- [x] #4 modules/aws/identity_center.py no longer imports integrations.aws.identity_store
- [x] #5 tests/unit/modules/aws/test_identity_center_handler.py is retargeted to patch build_identity_center_adapter, with new cases covering each bridge's success, non-success, and PERMANENT_ERROR-conflict paths, plus synchronize()'s DirectoryUsersUnavailableError path
- [x] #6 ruff, mypy (no new errors) and pytest pass with output recorded; a grep of this file shows zero references to integrations.aws.identity_store
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (re-read in full 2026-09-14, post-TASK-25.2.3.2.1): app/modules/aws/identity_center.py (355 lines); app/packages/aws_platform/adapters/identity_center.py (306 lines -- create_user:113, delete_user:126, list_users:156, create_group_membership:182, delete_group_membership:193, build_identity_center_adapter:296); app/modules/provisioning/entities.py (99 lines -- the kwargs splat at :61, the `if response:` truthiness test at :62); app/modules/provisioning/users.py (81 lines -- DirectoryUsersUnavailableError:15, the already-migrated aws branch at :56-69 that this slice mirrors); app/integrations/aws/identity_store.py (legacy -- create_user:49, delete_user:74, list_users:138, create_group_membership:194, delete_group_membership:217); app/integrations/aws/client.py (handle_aws_api_errors:236 returning literal False at :283; classify_aws_error:196 with ConflictException at :217-219); app/utils/filters.py (get_nested_value:28, preformat_items:124); app/tests/unit/modules/aws/test_identity_center_handler.py (453 lines).

## Finding 1 -- the kwargs splat is the real work of this slice (top risk, resolved)

`entities.provision_entities` calls `function(**entity, **kwargs)` at entities.py:61 -- it splats the ENTIRE entity dict, not a curated subset. Every legacy `identity_store.*` write carried a `**kwargs` catch-all that silently absorbed the surplus keys. The adapter's methods have strict signatures and would raise `TypeError: unexpected keyword argument` on the first entity. Surplus keys per call site:

- :155 create_user -- entity is a Google member dict (primaryEmail, name, ...) plus preformat_items additions (email, log_user_name, first_name, family_name). Adapter takes email/first_name/family_name. Surplus: primaryEmail, log_user_name, every Google member key.
- :171 delete_user -- entity is a raw Identity Store user dict (UserId, UserName, Emails, Name, ...) plus (user_id, log_user_name). Adapter takes user_id. Surplus: UserId, UserName, Emails, Name, log_user_name.
- :261 create_group_membership -- entity is {**google_member, user_id, group_id, log_user_name, log_group_name} (built at :247-258). Adapter takes group_id/user_id. Surplus: primaryEmail, log_*, Google keys.
- :282 delete_group_membership -- entity is {**target_membership (MembershipId, MemberId{...}), membership_id, log_user_name, log_group_name} (built at :271-280). Adapter takes membership_id. Surplus: MembershipId, MemberId, log_*.
- :329 create_user (provision_aws_users) -- entity is {primaryEmail, email, log_user_name, first_name, family_name} (built at :316-326). Surplus: primaryEmail, log_user_name.
- :348 delete_user (provision_aws_users) -- same shape as :171.

HUMAN DECISION 2026-09-14: the bridges take the adapter's named arguments plus a tolerant `**_ignored`, mirroring the legacy catch-all. Entity-dict construction and entities.py are NOT touched. Rationale: the entity dict is also forwarded verbatim to `log_to_sentinel({"entity": entity})` at entities.py:69/80, so narrowing the payloads would silently change the Sentinel event shape -- out of scope for a client migration.

## Finding 2 -- return-shape parity is exact; no shim needed

| call | legacy return | adapter result.data on success |
| --- | --- | --- |
| create_user | `execute_aws_api_call(...)["UserId"]` (str) | OperationResult[str] = UserId |
| delete_user | `response == {}` (bool) | OperationResult[bool] = True |
| create_group_membership | `response["MembershipId"]` (str) | OperationResult[str] = MembershipId |
| delete_group_membership | `response == {}` (bool) | OperationResult[bool] = True |

Returning `result.data` on success therefore preserves byte-for-byte what provision_entities stores in `{"entity": entity, "response": response}` at entities.py:72. On failure the legacy `handle_aws_api_errors` decorator returned literal `False` (client.py:283) for every exception family; the bridges return `False` explicitly, preserving the False-swallow so provision_entities logs `provision_entity_failed`, emits the failed Sentinel event, and continues the loop.

## Finding 3 -- ConflictException

`classify_aws_error` maps ConflictException to PERMANENT_ERROR (client.py:217-219), where it previously propagated as a raised ClientError and was then swallowed to `False` by the legacy decorator. The bridges' generic non-success branch already returns `False`, so an "already exists" conflict on create_user / create_group_membership stays a failed-but-non-fatal entity -- the same observable outcome as today, now logged with status and error_code instead of a bare `aws_client_error`. Documented in both bridge docstrings per the parent task's comment #1.

## Finding 4 -- test blast radius is exactly one file

`tests/unit/modules/aws/test_identity_center_handler.py` is the ONLY test file that patches `modules.aws.identity_center.identity_store` (decorator sites at :78, :112, :143, :302, :435). Verified by grep: `tests/unit/modules/aws/test_aws_command_handler.py` patches `modules.aws.aws.identity_store` and `tests/integration/jobs/test_scheduled_tasks_integration.py` patches `jobs.scheduled_tasks.identity_store` -- both belong to TASK-25.2.3.2.4 and stay untouched by this slice.

## Finding 5 -- caller error handling deliberately out of scope

synchronize() gains a typed raise where it previously crashed with TypeError (pinned by the characterization test at :436). Neither caller catches it: jobs/scheduled_tasks.py:150 and modules/aws/groups.py:76 (a Slack handler that has already replied "Synchronization Initiated"). HUMAN DECISION 2026-09-14: leave as-is, add no caller-side handling. The provisioning feature is frozen -- the access feature takes over this business capability once the vendor-SDK client migration reaches its end state -- so provisioning keeps only the minimum needed to stay working. Net effect of this slice at those callers is unchanged crash surface with better diagnostics.

## Ordered Steps

### Step 1 -- imports (app/modules/aws/identity_center.py)
- Delete `from integrations.aws import identity_store` (:5).
- Add `from packages.aws_platform.adapters.identity_center import build_identity_center_adapter`.
- Add `from typing import Any` for the `**_ignored: Any` annotations.
- DirectoryUsersUnavailableError needs NO new import: the module already imports `users` at :6, so reference `users.DirectoryUsersUnavailableError` (simplest, no import churn).

### Step 2 -- the four bridges (new, module-private, placed after `logger` at :9, before synchronize)
Each builds the adapter at call time (never at import -- adapter docstring :8-9), calls exactly one method, returns `result.data` on success, logs and returns `False` otherwise.

```
def _create_user(email: str, first_name: str, family_name: str, **_ignored: Any) -> str | bool:
    """Adapt a provision_entities entity dict onto the adapter's create_user.

    Surplus entity keys are absorbed and ignored, as the legacy client's **kwargs
    did. A non-success result -- including the PERMANENT_ERROR that an "already
    exists" ConflictException now produces -- returns False, so provision_entities
    records a failed entity and the sync continues.
    """
    result = build_identity_center_adapter().create_user(
        email=email, first_name=first_name, family_name=family_name
    )
    if not result.is_success:
        logger.error(
            "create_user_failed",
            status=result.status.value,
            error_code=result.error_code,
            error=result.message,
        )
        return False
    return result.data or False
```

- `_delete_user(user_id: str, **_ignored: Any) -> bool` -> `delete_user(user_id=user_id)`; `return bool(result.data)` on success.
- `_create_group_membership(group_id: str, user_id: str, **_ignored: Any) -> str | bool` -> `create_group_membership(group_id=group_id, user_id=user_id)`; carries the same ConflictException note as _create_user.
- `_delete_group_membership(membership_id: str, **_ignored: Any) -> bool` -> `delete_group_membership(membership_id=membership_id)`; `return bool(result.data)`.

`result.data or False` (not bare `result.data`) keeps the annotated return type `str | bool` instead of `str | None`, and preserves the legacy falsy-on-empty behavior.

### Step 3 -- synchronize()'s two list_users call sites (:70 and :79)
Mirror modules/provisioning/users.py:56-69 exactly (the pattern TASK-25.2.3.2.1 established). `log` is bound at :37 and is in scope at both sites.

```
target_users_result = build_identity_center_adapter().list_users()
if not target_users_result.is_success:
    log.error(
        "list_users_failed",
        error_code=target_users_result.error_code,
        error=target_users_result.message,
    )
    raise users.DirectoryUsersUnavailableError(
        target_users_result.message, target_users_result.error_code
    )
target_users = target_users_result.data or []
```

:79 sits inside `if enable_users_sync:` and gets the identical treatment (re-listing after sync_users). Use a distinct local name at each site so mypy sees one type per binding.

### Step 4 -- the six provision_entities call sites (swap the callable only; every other kwarg unchanged)
- :155 `identity_store.create_user` -> `_create_user`
- :171 `identity_store.delete_user` -> `_delete_user`
- :261 `identity_store.create_group_membership` -> `_create_group_membership`
- :282 `identity_store.delete_group_membership` -> `_delete_group_membership`
- :329 `identity_store.create_user` -> `_create_user`
- :348 `identity_store.delete_user` -> `_delete_user`

`modules/provisioning/entities.py` is NOT modified (AC#3).

### Step 5 -- tests (app/tests/unit/modules/aws/test_identity_center_handler.py)
Retarget existing:
- The three synchronize tests (:81, :115, :146): swap `@patch("modules.aws.identity_center.identity_store")` for `@patch("modules.aws.identity_center.build_identity_center_adapter")`; `mock_identity_store.list_users.return_value = []` becomes `mock_build.return_value.list_users.return_value = OperationResult.success(data=[])`.
- `TestProvisionAwsUsers` (:303): DROP the `@patch(...identity_store)` decorator and the `mock_identity_store` parameter from all six methods. These tests patch `entities` wholesale, so provision_entities is a Mock and the bridges are never invoked -- no adapter patch is needed at all.
- `TestSyncUsers` / `TestSyncGroups` (:174, :235): unchanged (they never referenced identity_store), plus one new assertion each that the correct bridge object was passed (see below).
- `test_should_raise_when_list_users_returns_false_before_sync` (:436, the TASK-25.2.1 characterization pin): rewrite as `test_should_raise_when_target_user_listing_fails_before_sync` -- adapter returns `OperationResult.error(OperationStatus.TRANSIENT_ERROR, message=..., error_code=...)`; assert `pytest.raises(users.DirectoryUsersUnavailableError)` and that message/error_code round-trip. Replaces the `pytest.raises(TypeError)` characterization with the new contract.

New bridge-level cases (call the bridges directly, patching `modules.aws.identity_center.build_identity_center_adapter`), per bridge:
- success returns the adapter's data (UserId / True / MembershipId / True);
- SURPLUS-KEY case -- the Finding 1 regression guard: call the bridge with the full realistic entity dict (e.g. `_create_user(**{"email": ..., "first_name": ..., "family_name": ..., "primaryEmail": ..., "log_user_name": ..., "name": {...}})`), assert it does not raise TypeError and that the adapter was called with exactly the named arguments;
- non-success (TRANSIENT_ERROR) returns False and logs status + error_code;
- PERMANENT_ERROR/ConflictException returns False for `_create_user` and `_create_group_membership` specifically (AC#2).
Plus `test_should_pass_the_local_bridges_to_provision_entities`: asserts each of the six call sites received the right bridge callable (guards against a half-done swap).

Docstrings describe behavior, stub strategy and assertion rationale only -- no task ids or plan step numbers (testing-standards).

### Step 6 -- verification
From app/: `uv run ruff check .`; `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` (compare against the 87-error/31-file baseline recorded by TASK-25.2.3.2.1 -- zero new errors in modules/aws); `uv run pytest tests --ignore=tests/smoke`; and `rg -n "identity_store" app/modules/aws/identity_center.py` expecting zero hits (AC#6). Record all four outputs in the task notes at finalization.

## AC Traceability
- AC#1 (two list_users sites raise DirectoryUsersUnavailableError) -> Step 3 -> tests: the three retargeted synchronize tests (happy path) + `test_should_raise_when_target_user_listing_fails_before_sync` (failure path).
- AC#2 (four bridges: map kwargs, return data or False, incl. PERMANENT_ERROR conflict) -> Step 2 -> tests: the per-bridge success / surplus-key / non-success / conflict cases.
- AC#3 (all six provision_entities sites use the bridges; entities.py unchanged) -> Step 4 -> test: `test_should_pass_the_local_bridges_to_provision_entities` + the untouched TestSyncUsers/TestSyncGroups/TestProvisionAwsUsers suites still passing.
- AC#4 (no integrations.aws.identity_store import) -> Step 1 -> verified by the Step 6 grep.
- AC#5 (test file retargeted with the new cases) -> Step 5.
- AC#6 (gates pass, zero identity_store references) -> Step 6.

## Test Matrix
- Happy path: each bridge returns the adapter's payload; synchronize() completes with a successful listing.
- Boundary: an empty-but-successful `list_users()` (`data=[]`) must NOT raise -- only `not is_success` raises; this distinguishes "zero users" (valid) from "listing failed", a distinction the old TypeError crash conflated. Also `data=None` on a success result -> bridge returns False (falsy), recorded as a failed entity rather than crashing.
- Failure: TRANSIENT_ERROR from each of the five adapter methods -> bridges return False / synchronize raises.
- Idempotency/conflict: PERMANENT_ERROR with error_code "ConflictException" on create_user and create_group_membership -> False, sync continues (the behavior change carried from TASK-25.2.3.1).
- Signature tolerance: surplus entity keys absorbed by `**_ignored` at all four bridges (the Finding 1 guard).

## Assumptions and How to Verify
1. Assumes `OperationStatus` is imported in the test file from `infrastructure.operations` alongside `OperationResult` -- verify with `rg -n "from infrastructure.operations" app/tests/unit/modules/provisioning/test_provisioning_users.py`, which already uses this exact pattern after TASK-25.2.3.2.1.
2. Assumes no production caller depends on `sync_users` / `sync_groups` / `provision_aws_users` returning the legacy `False` response value in a way the identical `result.data` would change -- verified: the only consumers are modules/aws/users.py:62 (json.dumps of the provision_entities list) and jobs/scheduled_tasks.py:150 / modules/aws/groups.py:76 (return value discarded).
3. Assumes `modules/aws/identity_center.py` currently contributes zero errors to the mypy baseline, so "no new errors" is measurable -- confirm by diffing the Step 6 mypy run against the 87-error baseline.
4. Assumes the Google member dicts reaching :155/:261 are plain dicts (splat-able). Verified: `filters.preformat_items` does `item[new_key] = ...` and provision_entities does `**entity`, both of which already require dicts today, and groups.py builds them via `_google_groups_to_legacy_shape`.

## Blast Radius and Rollback
- Blast radius: one production file. The AWS Identity Center sync (scheduled job + the `/aws groups sync` and `/aws users` Slack commands). A regression surfaces as either a spurious DirectoryUsersUnavailableError on a healthy store, a TypeError from an unabsorbed entity key (the Finding 1 risk, guarded by the surplus-key tests), or entities silently recorded as failed.
- Rollback: a single `git revert` of this slice's PR fully restores prior behavior -- no schema change, no data migration, and integrations/aws/identity_store.py still exists until TASK-25.2.3.2.4.
- Ordering: depends only on TASK-25.2.3.1 (Done). Independent of and parallelizable with .2.1 (already merged) and .2.3; must precede .2.4.

## Size-Gate Arithmetic (PASSES)
- Production files touched: 1 (app/modules/aws/identity_center.py).
- Production LOC changed: imports ~3 + four bridges ~48 + two list_users branches ~14 + six callable swaps ~6 = approx. 71 LOC.
- Subsystems crossed: 1.
- Mechanical/behavior mix: the callable swap and the typed-raise behavior change are the same uniform treatment applied across one file, not two separable refactors.
- Verdict: far under the ~400 LOC / ~10 file / two-subsystem thresholds; independently shippable and revertible.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed and why:
- app/modules/aws/identity_center.py (only production file touched): removed the integrations.aws.identity_store import; added build_identity_center_adapter and typing.Any imports.
- Added four module-private bridges: _create_user, _delete_user, _create_group_membership, _delete_group_membership. Each takes the adapter's named arguments plus **_ignored, because provision_entities splats each whole entity dict into the callable (entities.py:61).
- On success each bridge returns result.data, which is the same value the legacy function returned (UserId / True / MembershipId / True). On any non-success it returns False and logs status, error_code and message.
- ConflictException now arrives as PERMANENT_ERROR, so both create bridges return False for it: the entity is recorded as failed and the sync continues. This is documented in both create-bridge docstrings.
- Deviation from plan Step 3: the two list_users call sites in synchronize() share one helper, _list_target_users(log), instead of repeating the block. Behaviour is unchanged: on non-success it logs list_users_failed and raises users.DirectoryUsersUnavailableError(message, error_code); otherwise it returns data or [].
- All six provision_entities call sites now pass the bridges: sync_users create and delete, sync_groups membership create and delete, provision_aws_users create and delete. entities.py is unchanged.

Evidence (run from app/):
- rg -n identity_store modules/aws/identity_center.py -> no hits.
- uv run ruff check . -> All checks passed! ruff format --check on the file reports it already formatted.
- uv run pytest tests/unit/modules/aws/test_identity_center_handler.py -> 41 passed (30 failed / 11 passed before the implementation).
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 87 errors in 31 files (checked 355 source files). This equals the baseline recorded by TASK-25.2.3.2.1, with zero errors in modules/aws.
- make test (human-run, CI-shaped) -> full suite green.
- uv run pytest tests --ignore=tests/smoke (single process) -> 6 failed, 3411 passed. The 6 are known test-order state leaks tracked by TASK-90, not caused by this change:
  - tests/modules/webhooks/test_webhooks_aws_sns.py: 3 failures.
  - tests/unit/infrastructure/directory/test_google.py: 3 failures.
  - Both files pass when run on their own (111 passed).

Remaining for the human:
- Review and commit. The agent ran no git commands.
- Only a human moves the task to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 12:53
---
2026-09-14 planning pass. Three human decisions recorded, plus one AC correction.

(1) AC#3 corrected with explicit human approval: it said 'four entities.provision_entities call sites', but there are six. provision_aws_users passes identity_store.create_user at :329 and identity_store.delete_user at :348, which this task's own description already lists. Leaving them out would make AC#4 (no identity_store import in the file) unsatisfiable. Still four bridge functions, reused across six call sites. No other AC was reworded.

(2) Bridge signature style: bridges take the adapter's named arguments plus a tolerant **_ignored. entities.provision_entities splats the WHOLE entity dict (function(**entity, **kwargs) at entities.py:61) and the legacy identity_store functions each had a **kwargs catch-all that absorbed the surplus; the adapter's signatures are strict and would raise TypeError on the first entity. The rejected alternative -- narrowing the entity dicts at each call site -- was declined because the same dict is forwarded verbatim to log_to_sentinel({'entity': entity}) at entities.py:69/80, so narrowing would silently change the Sentinel event shape.

(3) Caller error handling is out of scope. synchronize() gains a typed raise where it previously crashed with TypeError, and neither caller catches it (jobs/scheduled_tasks.py:150; modules/aws/groups.py:76, a Slack handler that has already replied 'Synchronization Initiated'). Human direction: the provisioning feature is frozen and will not be migrated as-is -- the access feature takes over this business capability once the vendor-SDK client migration reaches its end state -- so provisioning keeps only the minimum needed to keep working. Net effect at those callers is unchanged crash surface with better diagnostics. No follow-up task raised, per that direction.

Also verified during planning: return-shape parity between result.data and the legacy returns is exact at all four writes, so no shim is needed; and tests/unit/modules/aws/test_identity_center_handler.py is the only test file patching modules.aws.identity_center.identity_store (the other identity_store test references target modules.aws.aws and jobs.scheduled_tasks, both owned by TASK-25.2.3.2.4).
---

created: 2026-09-14 13:04
---
2026-09-14: failing tests authored (TDD red) in app/tests/unit/modules/aws/test_identity_center_handler.py; no production code touched.

Evidence (from app/): uv run pytest tests/unit/modules/aws/test_identity_center_handler.py -q -> 30 failed, 11 passed. All 30 failures are AttributeError: modules.aws.identity_center has no build_identity_center_adapter / _create_user / _delete_user / _create_group_membership (26 on the adapter patch target, 4 on bridge identity asserts). The 11 passing tests cover unchanged sync_users/sync_groups/provision_aws_users behaviour. uv run ruff check -> All checks passed; ruff format applied to this file.

Mapping to ACs:
- AC#1: the three synchronize tests retargeted to the adapter; new test_should_raise_when_target_user_listing_fails_before_sync (replaces the TypeError characterization), test_should_raise_when_user_relisting_after_user_sync_fails, test_should_treat_an_empty_successful_user_listing_as_zero_users, test_should_pass_the_post_sync_user_listing_to_group_sync.
- AC#2: TestCreateUserBridge, TestDeleteUserBridge, TestCreateGroupMembershipBridge, TestDeleteGroupMembershipBridge -- success, surplus-entity-key tolerance, non-success -> False, logged status/error_code, and ConflictException PERMANENT_ERROR -> False for both creates; plus success-with-no-UserId -> False.
- AC#3: identity asserts that all six provision_entities call sites receive the bridges (TestSyncUsers, TestSyncGroups, and two new TestProvisionAwsUsers cases).
- AC#5: the identity_store patch removed from TestProvisionAwsUsers (entities is mocked, so no adapter patch is needed there).
Tests reference the bridges as module-private names _create_user, _delete_user, _create_group_membership, _delete_group_membership, as specified in the plan.
---
<!-- COMMENTS:END -->
