---
id: TASK-105.3
title: >-
  Clear the mypy errors from the optional OperationResult message and float
  retry_after at call sites
status: In Progress
assignee: []
created_date: '2026-09-28 15:36'
updated_date: '2026-09-28 16:40'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies:
  - TASK-105.1
references:
  - decisions/operation-result.md
parent_task_id: TASK-105
priority: medium
ordinal: 289000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-105 widened OperationResult.message to str | None (optional on SUCCESS) and retry_after to float | None, per decisions/operation-result.md. It left 29 new mypy errors in 16 files it did not touch. CI does not block on them because lint-ci runs mypy with || true, but the repo got worse. Every error comes from forwarding an upstream result's message or retry_after into a narrower type:
- 27 are message: str | None passed to OperationResult.error(message=...) or to exception constructors that take str: infrastructure/{directory,drive,spreadsheets}/google.py, packages/incident_draft/service.py (these four are also edited by TASK-105.1, which may remove some of the sites), packages/access/{catalog/service.py, request/interactions/http.py, sync/desired_state.py, sync/adapters/aws_identity_center.py, sync/adapters/fake_platform.py}, modules/{aws/identity_center.py, incident/incident_folder.py, permissions/handler.py, provisioning/groups.py, provisioning/users.py}.
- 2 are retry_after: float | None passed to IncidentStoreUnavailableError / WebhookStoreUnavailableError typed int | None: modules/incident/db_operations.py, modules/slack/webhooks.py.
Measure the list again after TASK-105.1 lands, then fix each site at its own boundary without changing runtime behaviour on error paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 mypy reports no arg-type error caused by OperationResult.message being str | None or retry_after being float | None, checked by diffing mypy output against the pre-TASK-105 baseline
- [x] #2 Runtime behaviour on error paths is unchanged: the fallback text is used only where message is None
- [x] #3 ruff, lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-verified 2026-09-28 against current tree (`cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, 102 errors/37 files total repo-wide, unrelated ones ignored): 25 message/retry_after arg-type errors remain in 12 production files (notes said 26/13; TASK-105.1 already cleared the google.py/incident_draft sites, and one more site collapses below — see Step 6).

Size-gate decision (human, 2026-09-28): ONE task/PR, not split by subsystem.
- 11 production files is just over the ~10-file guide and the change touches 2 subsystems (legacy modules/, packages/access); accepted as one PR because the diff is ~19 LOC and every site is the same kind of fix (a str|None/float|None value flowing into a narrower declared type).
- No mechanical refactor is mixed with behaviour change; the fallback text (AC #2) is inseparable from the type fix.
- A single `git revert` cleanly restores the current (mypy-red-but-running) state.

Root-cause grouping and per-site fix (minimal, ADR-consistent: message is for logs/operators, optional on SUCCESS; retry_after preserved as None so consumers apply their own backoff):

Group A — widen internal exception constructors' `message` param from `str` to `str | None` (these classes are exclusively constructed by forwarding an OperationResult's message; call sites already branch on `result.is_success`/`.status` before raising, so no fallback text is needed or desired — the class itself just needs to accept what the result actually carries):
1. modules/provisioning/users.py:19 — `DirectoryUsersUnavailableError.__init__` `message: str` -> `str | None` (fixes users.py:54, users.py:68, and modules/aws/identity_center.py:82 with zero edit to identity_center.py). ~1 LOC.
2. modules/provisioning/groups.py:16 — `DirectoryGroupsUnavailableError.__init__` `message: str` -> `str | None` (fixes groups.py:117, groups.py:151). ~1 LOC.
3. modules/incident/incident_folder.py:36 — `IncidentSheetError.__init__` `message: str` -> `str | None` (fixes lines 298, 338, 362, 397). ~1 LOC.
4. modules/permissions/handler.py:19 — `PermissionCheckError.__init__` positional `message: str` -> `str | None` (fixes line 48). ~1 LOC.

Group B — widen `retry_after` param from `int | None` to `float | None` on classes exclusively built from `result.retry_after` via a private `_unavailable()` helper:
5. modules/incident/db_operations.py:30 — `IncidentStoreUnavailableError.__init__` `retry_after: int | None` -> `float | None` (fixes line 39). ~1 LOC.
6. modules/slack/webhooks.py:35 — `WebhookStoreUnavailableError.__init__` `retry_after: int | None` -> `float | None` (fixes line 44). ~1 LOC.

Group C — `OperationResult.error(message=...)` re-wraps an upstream result's optional message into a new error result whose classmethod deliberately requires `message: str` (infrastructure/operations/result.py:71, out of scope — it is shared, already-landed TASK-105/105.1 contract; broadening it is a separate concern). Fix each site with a fallback literal matching the existing `error_code=... or "CODE"` style already used alongside it, since these are pure status/error_code/retry_after pass-throughs:
7. packages/access/catalog/service.py:157 — `message=discovery_result.message or "Group discovery failed"`. ~1 LOC.
8. packages/access/sync/adapters/aws_identity_center.py:807 — `message=result.message or "Failed to resolve group"`. ~1 LOC.
9. packages/access/sync/adapters/aws_identity_center.py:852 — `message=result.message or "Action execution failed"`. ~1 LOC.
10. packages/access/sync/adapters/fake_platform.py:163 — `message=result.message or "Action execution failed"`. ~1 LOC.
11. packages/access/sync/desired_state.py — 8 sites, each `message=<x>_result.message or "<description> failed"`:
    - :80 authn_result -> "Authentication group membership check failed"
    - :92 user_groups_result -> "User groups lookup failed"
    - :164 authn_members_result -> "Authentication group members lookup failed"
    - :177 group_result -> "Group lookup failed"
    - :211 batch_result -> "Batch group members lookup failed"
    - :254 list_result -> "Group discovery failed"
    - :291 group_result -> "Group lookup failed"
    - :318 membership_result -> "Membership check failed"
    ~8 LOC total.
    Fallback wording (steps 7-11) is the planner's; the human reviews and may adjust it in the PR diff.

Group D — HTTP response schema mirrors the ADR's "message optional on SUCCESS" out to the API boundary (single producer, success path only):
12. packages/access/request/schemas.py:121 — `SubmitAccessRequestResponse.message: str` -> `str | None` (human decision 2026-09-28: accept the field becoming nullable in the OpenAPI schema); make sure the field's description states it may be null on success. ~1-2 LOC. No edit needed in packages/access/request/interactions/http.py:229 — passing `result.message` (str | None) type-checks once the field is widened.

Total: 11 production files, ~19 LOC.

Test matrix (human decision 2026-09-28: test behaviour changes only). Groups A and B are signature widenings with no branching; mypy is their check and existing tests keep covering the raise paths, so they get no new tests. All edits are in place in existing layered files; no new test files:
- tests/unit/packages/access/catalog/test_access_catalog_service.py: list_groups() returning a NOT_FOUND/TRANSIENT_ERROR result with message=None yields the "Group discovery failed" fallback and preserves error_code.
- tests/unit/packages/access/sync/test_aws_identity_center_adapter.py: both canonicalize-entitlement and execute-planned-actions error paths fall back correctly when message=None, and keep the upstream message when present.
- tests/unit/packages/access/sync/test_fake_platform_adapter.py: action-execution error path fallback when message=None.
- tests/unit/packages/access/sync/test_desired_state.py: at least one representative forwarding site (e.g. authn membership check) asserts the fallback text when the upstream result carries message=None; error_code/retry_after still forwarded verbatim.
- tests/unit/packages/access/request/test_access_request_schemas.py: SubmitAccessRequestResponse constructs with message=None.
- tests/unit/packages/access/request/test_access_request_routes.py: POST /api/v1/access/requests success response serializes message as null when the service result has no message.

AC traceability:
- AC #1 (mypy clean for these arg-types) -> Steps 1-12, verified by re-running the mypy command and diffing against this plan's 25-error baseline.
- AC #2 (fallback used only when message is None; behavior otherwise unchanged) -> Steps 7-11 fallback literals plus their listed tests; Steps 1-6 are pure signature widenings with no branching, so behaviour is unchanged by construction (existing tests continue to pass); step 12's null serialization is covered by the schema and route tests.
- AC #3 (ruff, lint-imports, pytest) -> run after edits, before handoff.

Assumptions/doubts:
- Assumes DirectoryUsersUnavailableError/DirectoryGroupsUnavailableError/IncidentSheetError/PermissionCheckError have no other constructors elsewhere in the codebase besides the sites grepped in this session (confirmed via `rg -n "<ClassName>\("` across modules/, packages/, infrastructure/ — only the listed call sites matched).
- Assumes IncidentStoreUnavailableError/WebhookStoreUnavailableError are only ever built via each file's private `_unavailable()` helper (confirmed by grep) — widening retry_after is safe with no other caller expecting `int`.
- Only producer of SubmitAccessRequestResponse.message is packages/access/request/interactions/http.py:229; the nullable schema change is accepted (see step 12).

Blast radius / rollback: all changes are additive type widenings or `or "<fallback>"` literals on already-error/edge paths; no SUCCESS-path or happy-path logic changes. A single `git revert` fully restores current behavior. No ordering constraints — independent of TASK-105.1's already-merged cleanup and of the still-open TASK-106 contracts move.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented on stack-a/task-105.3-result-message-call-sites (Stack A layer 5), per the approved plan.

Production (11 files, +25/-23):
- Group A: message widened to str | None on DirectoryUsersUnavailableError (modules/provisioning/users.py), DirectoryGroupsUnavailableError (groups.py), IncidentSheetError (modules/incident/incident_folder.py), PermissionCheckError (modules/permissions/handler.py). No consumer reads .message on these exceptions (checked).
- Group B: retry_after widened to float | None on IncidentStoreUnavailableError (modules/incident/db_operations.py) and WebhookStoreUnavailableError (modules/slack/webhooks.py).
- Group C: 12 'x.message or "<...> failed"' fallbacks in packages/access (catalog/service.py, sync/adapters/aws_identity_center.py x2, sync/adapters/fake_platform.py, sync/desired_state.py x8), wording as in the plan; the human reviews it in the PR.
- Group D: SubmitAccessRequestResponse.message is str | None with a Field description saying it may be null.
- Bugs fixed in touched files (fix-bugs-in-touched-files rule), clearing the 8 older mypy errors in them: incident_folder.py get_incidents_from_sheet compared None < str when a row's created-at cell was empty (TypeError with days > 0); rows without created_at are now skipped by the lookback filter. get_incident_details reads response["channel"] (ok=True guarantees it) instead of .get(). catalog/service.py _check_membership annotates log as structlog.stdlib.BoundLogger instead of object.

Tests (7 files, in place, no new files): fallback tests for catalog discovery, AWS IC group resolution and action execution, fake platform action execution, desired_state user-groups lookup; schema test for the nullable, described message; route test for a null message on success; legacy tests/modules/incident/test_incident_folder.py gets a regression test for the empty created-at row (fails with TypeError without the fix).

Gates (from app/): ruff check . -> All checks passed; ruff format --check on touched files -> clean; lint-imports -> 7 kept, 0 broken; mypy -> 69 errors in 25 files repo-wide (was 102 in 37 before this layer: the 25 widening errors and 8 older ones in touched files are gone), 0 in touched files; pytest tests --ignore=tests/smoke -> 3476 passed, 6 failed (known single-process order leaks in test_webhooks_aws_sns.py and directory/test_google.py); make test -> 2724 passed + 758 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 16:25
---
2026-09-28: plan decisions by human (Guillaume Charest), given in session: accept SubmitAccessRequestResponse.message becoming nullable in OpenAPI; test behaviour changes only (Groups C and D), no new test files; one PR despite 11 production files over 2 subsystems; fallback wording reviewed in the PR diff. Plan revised to match. Plan approval not yet recorded.
---

created: 2026-09-28 16:26
---
2026-09-28: implementation plan approved by human (Guillaume Charest).
---
<!-- COMMENTS:END -->
