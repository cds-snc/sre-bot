---
id: TASK-25.2.4.1
title: Build the Organizations and SSO-Admin adapters with Stubber tests
status: In Progress
assignee: []
created_date: '2026-09-14 17:38'
updated_date: '2026-09-14 19:10'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/packages/aws_platform/adapters/identity_center.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1a of TASK-25.2.4 (build phase, expand only, no caller changes). Create packages/aws_platform/adapters/organizations.py and packages/aws_platform/adapters/sso_admin.py following the shape proven by packages/aws_platform/adapters/identity_center.py (typed client from get_aws_client, OperationResult returns, try/except + classify_aws_error, botocore.stub.Stubber tests). Organizations carries list_organization_accounts, get_account_details, get_account_tags and healthcheck (integrations/aws/organizations.py:12,53,67,80); get_active_account_names (organizations.py:22) and get_account_id_by_name (organizations.py:34) have zero production callers (re-grepped 2026-09-14, get_account_id_by_name's only caller was deleted by TASK-25.2.3.2.4) and are dropped, not ported. SSO-Admin carries create_account_assignment, delete_account_assignment and list_account_assignments_for_principal (sso_admin.py:33,65,94), each built with role_arn=settings.SERVICE_ROLE_MAP['sso-admin']; list_accounts_for_provisioned_permission_set (sso_admin.py:122) and get_predefined_permission_sets travel only if re-grep still shows zero callers -> re-verify before dropping, current grep shows none. No adapter provider registry: reuse the established build_<adapter>() factory-function pattern (e.g. build_organizations_adapter(), build_sso_admin_adapter()), not app/infrastructure/services/providers.py -- packages/aws_platform is the documented provisional seam (TASK-25.2 description, TIER RULES).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 packages/aws_platform/adapters/organizations.py returns OperationResult from every operation, builds its client only through get_aws_client, and has Stubber unit tests for each operation plus classification paths
- [x] #2 packages/aws_platform/adapters/sso_admin.py returns OperationResult from every operation, builds its client only through get_aws_client, and has Stubber unit tests for each operation plus classification paths
- [x] #3 get_active_account_names and get_account_id_by_name are re-grepped for callers and dropped (not ported) if still unused; list_accounts_for_provisioned_permission_set is re-grepped and dropped if still unused
- [x] #4 get_account_tags paginates Organizations ListTagsForResource across all pages (fixing the legacy organizations.py mirror's single unpaginated call), verified by a dedicated pagination Stubber test
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-14): app/packages/aws_platform/adapters/identity_center.py (306 LOC, landed TASK-25.2.3.1), its Stubber tests under app/tests/unit/packages/aws_platform/test_aws_platform_identity_center_{operations,groups_join,provider}.py, app/integrations/aws/{organizations.py (96 LOC), sso_admin.py (145 LOC), client.py, settings.py}, app/tests/integrations/aws/{test_organizations.py (424 LOC, 20 tests), test_sso_admin.py (84 LOC, 7 tests)}, callers modules/aws/{ops_group_assignment.py, spending.py, aws_account_health.py}, decisions/testing.md, TASK-50, and TASK-25.2.3's closed plan/notes.

TEST-TOOL DECISION (human decision 2026-09-14, applies to every TASK-25.2.4.x subtask): botocore.stub.Stubber, the same as TASK-25.2.3.1. This is a deliberate standard, not ADR compliance. decisions/testing.md:24 names moto for unit-testing boto3 adapters, but: (a) moto is only installed as moto[dynamodb]>=5.2.2 and nothing in app/tests uses it, and its adoption is tracked by TASK-50 (still To Do); (b) TASK-25.2.3 already uses Stubber; (c) organizations/sso_admin make plain request/response calls with no server-side semantics (ConditionExpression, GSI, TTL) that a stub can't reproduce. Using one tool for every adapter in this series means the later move to moto is a single uniform change.

ADAPTER SHAPE REUSED VERBATIM FROM identity_center.py (no reinvention):
- Class holds typed client(s) built once by the factory function, never at import (identity_center.py:46-54).
- `_map_sdk_exception(operation, exc)` staticmethod: classify_aws_error(exc) -> (status, error_code, retry_after), structlog warning, OperationResult.error(...) (identity_center.py:58-75).
- `_call[T](operation, fn)`: try/except (ClientError, BotoCoreError) -> OperationResult.success/._map_sdk_exception; anything else propagates (identity_center.py:77-82).
- `_paginate(paginator_name, response_key, **kwargs)`: client.get_paginator(name).paginate(**kwargs), flattens response_key list across pages, wrapped in `_call` (identity_center.py:84-98).
- Module-level `build_<name>_adapter()` factory: reads get_aws_settings().SERVICE_ROLE_MAP[<service>], calls get_aws_client(<service>, role_arn=...) (identity_center.py:296-306).
- SERVICE_ROLE_MAP already has "organizations" and "sso-admin" keys -> ORG_ROLE_ARN (integrations/aws/settings.py:109,111); get_aws_client already has Literal overloads for "organizations" and "sso-admin" (integrations/aws/client.py:73-87). No client.py or settings.py changes needed for this slice.

STEP 1 - app/packages/aws_platform/adapters/organizations.py (new file)
Class OrganizationsAdapter(client: OrganizationsClient) with role_arn read once by the factory (single client; no writes, so no no-retry client needed unlike identity_center).
- `list_organization_accounts() -> OperationResult[list[dict[str, Any]]]`: `_paginate("list_accounts", "Accounts")` (mirrors organizations.py:12-19, which already paginates correctly via `paginated=True, keys=["Accounts"]` - direct port, no behavior change).
- `get_account_details(account_id: str) -> OperationResult[dict[str, Any]]`: `_call("describe_account", lambda: client.describe_account(AccountId=account_id)["Account"])` (mirrors organizations.py:52-63; DescribeAccount is a single-object call, not paginated in the AWS API - no fix needed).
- `get_account_tags(account_id: str) -> OperationResult[list[dict[str, Any]]]`: `_paginate("list_tags_for_resource", "Tags", ResourceId=account_id)`. BUG FIX IN SCOPE: the legacy mirror (organizations.py:66-77) calls list_tags_for_resource once with no `paginated=True`, but Organizations' ListTagsForResource is paginated (boto3 paginator "ListTagsForResource" exists, response can include NextToken per AWS docs, verified via docs.aws.amazon.com/boto3 2026-09-14) - an account with more than one page of tags would silently lose tags today. The adapter's `_paginate` helper fixes this for free, same shape as list_organization_accounts.
- `healthcheck() -> OperationResult[bool]`: `_call("healthcheck", lambda: (client.list_accounts(MaxResults=1), True)[1])`, mirroring the healthcheck semantics of organizations.py:80-96 (healthy iff the call succeeds, regardless of whether it returns accounts) but through `_call` instead of a bespoke try/except - matches identity_center.py's `healthcheck()` pattern (single-page list, success-iff-no-exception).
- Dropped, not ported (re-grepped 2026-09-14, zero production callers found via `rg -n "organizations\.(get_active_account_names|get_account_id_by_name)" app/ --glob '!*/tests/*'`): `get_active_account_names` (organizations.py:22-31) and `get_account_id_by_name` (organizations.py:34-49). Confirms TASK-25.2.4's coordinator note.
- `build_organizations_adapter() -> OrganizationsAdapter`: `get_aws_client("organizations", role_arn=get_aws_settings().SERVICE_ROLE_MAP.get("organizations") or None)`.

STEP 2 - app/packages/aws_platform/adapters/sso_admin.py (new file)
Module-level `_get_predefined_permission_set(name: str, settings: AWSSettings) -> str` (private helper, ported from sso_admin.py:15-29's `get_predefined_permission_sets`, renamed to avoid confusion with the AWS API's own "permission set" objects and marked private since it's adapter-internal, not a public operation) mapping "write"/"read" to settings.SYSTEM_ADMIN_PERMISSIONS/VIEW_ONLY_PERMISSIONS, else pass-through.
Class SsoAdminAdapter(client: SSOAdminClient, instance_arn: str, system_admin_permissions: str, view_only_permissions: str):
- `create_account_assignment(user_id, account_id, permission_set, principal_type="USER") -> OperationResult[bool]`: `_call("create_account_assignment", lambda: client.create_account_assignment(InstanceArn=..., TargetId=account_id, TargetType="AWS_ACCOUNT", PermissionSetArn=_get_predefined_permission_set(permission_set, ...), PrincipalType=principal_type, PrincipalId=user_id)["AccountAssignmentCreationStatus"]["Status"] != "FAILED")`, direct port of sso_admin.py:33-61. No polling of describe_account_assignment_creation_status: keep today's behaviour of trusting the initial response, where IN_PROGRESS counts as success. Human decision 2026-09-14: the only caller (ops_group_assignment) hasn't been used in 3+ weeks, so do the minimum and reassess when the business feature moves to packages/.
- `delete_account_assignment(user_id, account_id, permission_set) -> OperationResult[bool]`: direct port of sso_admin.py:64-91, same shape.
- `list_account_assignments_for_principal(principal_id, principal_type="USER") -> OperationResult[list[dict[str, Any]]]`: `_paginate("list_account_assignments_for_principal", "AccountAssignments", PrincipalId=principal_id, PrincipalType=principal_type, InstanceArn=instance_arn)`, direct port of sso_admin.py:94-118 (already paginates correctly via `paginated=True, keys=["AccountAssignments"]` in the mirror - confirmed via boto3 docs the ListAccountAssignmentsForPrincipal paginator exists and the mirror already uses it correctly, no fix needed). BUG NATURALLY FIXED: this is the one legacy function missing `@handle_aws_api_errors` (sso_admin.py:94, inconsistent with its siblings at :32,:64,:121) - a ClientError today propagates raw and uncaught. The new adapter's uniform `_call`/`_paginate` wrapping fixes this automatically; no separate action needed since every operation goes through the same helper regardless of the legacy inconsistency.
- Dropped, not ported (re-grepped 2026-09-14, zero production callers via `rg -n "sso_admin\.(list_accounts_for_provisioned_permission_set|get_predefined_permission_sets)" app/ --glob '!*/tests/*'`): `list_accounts_for_provisioned_permission_set` (sso_admin.py:121-145). `get_predefined_permission_sets` (sso_admin.py:15-29) travels only as the private `_get_predefined_permission_set` helper above since create/delete_account_assignment still need it.
- `build_sso_admin_adapter() -> SsoAdminAdapter`: reads settings.SERVICE_ROLE_MAP.get("sso-admin"), settings.INSTANCE_ARN, settings.SYSTEM_ADMIN_PERMISSIONS, settings.VIEW_ONLY_PERMISSIONS; `get_aws_client("sso-admin", role_arn=...)`.

STEP 3 - Stubber tests: app/tests/unit/packages/aws_platform/test_aws_platform_organizations_operations.py (new file)
Real `boto3.client("organizations", region_name="ca-central-1", aws_access_key_id="testing", aws_secret_access_key="testing")` wrapped in `botocore.stub.Stubber`, `pytestmark = pytest.mark.unit`, one `TestX` class per operation matching identity_center.py's test file structure. Cases (see TEST MATRIX below) plus a `TestErrorClassification` class mirroring identity_center's (NOT_FOUND/UNAUTHORIZED/TRANSIENT/BotoCoreError/unmapped ClientError/programmer-error-propagates), run against `list_organization_accounts` as the representative operation (matches identity_center.py:667-846's single representative-operation pattern for the shared `_call`/`_map_sdk_exception` path).

STEP 4 - Stubber tests: app/tests/unit/packages/aws_platform/test_aws_platform_sso_admin_operations.py (new file)
Same shape as Step 3, operations create_account_assignment, delete_account_assignment, list_account_assignments_for_principal, plus one TestErrorClassification class run against list_account_assignments_for_principal.

TEST MATRIX (AC-traced; * = carried forward from the legacy test's pinned case per the "carry behavior-pinning cases forward" instruction, legacy file not touched - deleted wholesale later in .4.7)
| Case | Adapter op | New test | Legacy case carried |
|---|---|---|---|
| Happy path, single page | list_organization_accounts | test_list_organization_accounts_success_single_page | test_list_organization_accounts_success* |
| Pagination, two pages via NextToken | list_organization_accounts | test_list_organization_accounts_pagination_two_pages | test_list_organization_accounts_pagination* |
| Empty result | list_organization_accounts | test_list_organization_accounts_empty | test_list_organization_accounts_empty* |
| Happy path | get_account_details | test_get_account_details_success | test_get_account_details_success* |
| Happy path | get_account_tags | test_get_account_tags_success_single_page | test_get_account_tags_success* |
| Pagination, two pages via NextToken (NEW - the bug fix) | get_account_tags | test_get_account_tags_pagination_two_pages | none (new coverage) |
| Empty tags | get_account_tags | test_get_account_tags_empty | test_get_account_tags_empty_response* |
| Healthcheck success (with and without accounts) | healthcheck | test_healthcheck_succeeds_on_empty_and_nonempty_page | test_healthcheck_success*, test_healthcheck_empty_response* |
| Happy path | create_account_assignment | test_create_account_assignment_success_status_not_failed | test_create_assignment_for_user_returns_true_if_permissions_added_with_write/read* |
| FAILED status in response body (not an exception) | create_account_assignment | test_create_account_assignment_failed_status_returns_false | test_create_assignment_for_user_returns_false_if_permissions_failed* |
| Predefined permission set resolution (write/read/passthrough) | create_account_assignment | test_create_account_assignment_resolves_predefined_permission_sets | test_get_predefined_permission_sets* |
| Happy path | delete_account_assignment | test_delete_account_assignment_success_status_not_failed | test_delete_assignment_for_user_returns_true_if_permissions_added_with_write/read* |
| FAILED status in response body | delete_account_assignment | test_delete_account_assignment_failed_status_returns_false | test_delete_assignment_for_user_returns_false_if_permissions_failed* |
| Happy path, single page | list_account_assignments_for_principal | test_list_account_assignments_success_single_page | none (legacy file had no test for this function) |
| Pagination, two pages via NextToken | list_account_assignments_for_principal | test_list_account_assignments_pagination_two_pages | none |
| Empty result | list_account_assignments_for_principal | test_list_account_assignments_empty | none |
| NOT_FOUND (ResourceNotFoundException) classification | representative op per adapter | test_resource_not_found_classification | test_get_account_details_exception*, test_get_account_tags_exception* (generalized: legacy tests only asserted "returns False", new tests assert the specific OperationStatus) |
| UNAUTHORIZED (AccessDeniedException) classification | representative op per adapter | test_access_denied_classification | none (new coverage - not exercised by legacy tests) |
| TRANSIENT (ThrottlingException) classification with retry_after | representative op per adapter | test_throttling_classification_with_retry_after | none (new coverage) |
| BotoCoreError (EndpointConnectionError) -> TRANSIENT | representative op per adapter | test_botocore_connection_error_is_transient | none |
| Unmapped ClientError propagates | representative op per adapter | test_unmapped_client_error_propagates | none |
| Programmer error (e.g. KeyError) propagates | representative op per adapter | test_programmer_error_propagates | none |

Legacy cases NOT carried forward (behavior intentionally not preserved, both dropped functions): test_get_active_account_names_* (4 cases) and test_get_account_id_by_name_* (4 cases) - these test dropped, zero-caller functions; noted for TASK-25.2.4.7 as redundant once organizations.py is deleted. test_healthcheck_none_response*/test_healthcheck_exception* - the legacy mirror's healthcheck() has a bespoke try/except returning False; the new adapter's healthcheck goes through the same `_call`/OperationResult path as every other operation, so "exception" is now just another classification case covered by the shared TestErrorClassification suite rather than a bespoke healthcheck-specific exception test.

AC TRACEABILITY
- AC#1 (organizations.py adapter, OperationResult, get_aws_client-only, Stubber tests) <- Step 1 + Step 3, tests in test_aws_platform_organizations_operations.py
- AC#2 (sso_admin.py adapter, same bar) <- Step 2 + Step 4, tests in test_aws_platform_sso_admin_operations.py
- AC#3 (re-grep and drop get_active_account_names/get_account_id_by_name/list_accounts_for_provisioned_permission_set if still unused) <- re-grep commands documented in Steps 1-2 above, re-run once more immediately before implementation in case a new caller landed since 2026-09-14
- AC#4 (get_account_tags paginates ListTagsForResource across all pages) <- Step 1 (get_account_tags via _paginate) + Step 3, test test_get_account_tags_pagination_two_pages in test_aws_platform_organizations_operations.py
- Reverse check: test_get_account_tags_pagination_two_pages -> AC#4; every other organizations test -> AC#1; every sso_admin test -> AC#2; nothing tests AC#3 because it is a re-grep and removal step

ASSUMPTIONS (each with how to verify)
- Organizations ListTagsForResource pagination fix (get_account_tags) changes wire behavior (more tags returned for >1-page accounts) but not the OperationResult contract, so it's safe to ship in an expand-only slice with no caller yet depending on it - verify by confirming no caller reads get_account_tags before this PR merges (none do; spending.py's caller move is .4.4, later).
- sso-admin CreateAccountAssignment/DeleteAccountAssignment keep the legacy check on the initial response, with no polling of describe_account_assignment_creation_status/_deletion_status. Human-confirmed 2026-09-14 (bare minimum; the caller is effectively unused; see the TASK-25.2.4.3 notes).
- get_aws_client's existing Literal overloads and SERVICE_ROLE_MAP entries for "organizations"/"sso-admin" need no changes - verified directly by reading client.py:73-87 and settings.py:105-116 in this session.
- No infrastructure/services/providers.py registration needed - verified against identity_center.py precedent (module-level build_*_adapter() factory only) and TASK-25.2's TIER RULES section, same as recorded in the 25.2.4 coordinator plan.

BLAST RADIUS AND ROLLBACK
- Purely additive: two new adapter files plus two new test files, zero production callers wired in this slice (organizations.py and sso_admin.py mirrors keep serving all current traffic unchanged). A `git revert` of this PR is a clean no-op for production behavior.
- The one behavior difference from the legacy mirror (get_account_tags now paginates) has no observable effect until .4.4 migrates spending.py onto this adapter - it ships dormant.
- Known pre-existing risk, not introduced here: eager AssumeRole at adapter-build time (get_aws_client with role_arn assumes the role synchronously) - same as identity_center.py's established pattern, not a new concern for this slice.

SIZE ESTIMATE AND GATE VERDICT
- Production files: 2 new (organizations.py ~130-150 LOC incl. docstrings, sso_admin.py ~110-130 LOC incl. docstrings). Total production LOC: ~250-280, well under the ~400 LOC / ~10 file gate.
- Test files: 2 new (non-production LOC, not gated), roughly comparable in size to identity_center's operations test file scaled down for fewer operations (7 total ops here vs. 13 there).
- No caller files touched, no mechanical-refactor-plus-behavior-change mixing (this slice is 100% additive), single subsystem (packages/aws_platform/adapters).
- VERDICT: fits comfortably in one reviewable PR. No further decomposition needed.

VERIFICATION (run from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke

BUG-FIX POLICY (human decision 2026-09-14)
Fix any bug found in a file this slice touches, with a simple fix. If the fixes push the slice well past the size gate, stop and ask the human. In this slice that means the get_account_tags pagination fix (AC#4) and uniform error wrapping for list_account_assignments_for_principal. Bugs in caller files are recorded on the subtasks that own those files (.2, .4, .5).

OPEN QUESTIONS FOR HUMAN REVIEW
None. Polling, test tool and bug-fix scope were resolved 2026-09-14.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented packages/aws_platform/adapters/organizations.py and sso_admin.py on the identity_center.py shape (_map_sdk_exception, _call, _paginate, build_<name>_adapter factory).
- Re-grep before implementation (2026-09-14): get_active_account_names, get_account_id_by_name, list_accounts_for_provisioned_permission_set and get_predefined_permission_sets have no callers outside the legacy mirrors themselves; dropped, not ported. Predefined permission-set resolution travels as the private SsoAdminAdapter._get_predefined_permission_set.
- get_account_tags now paginates ListTagsForResource (AC#4); list_account_assignments_for_principal is now error-wrapped like its siblings.
- Tests: test_aws_platform_{organizations,sso_admin}_{operations,provider}.py, 33 tests. The provider tests go beyond the plan's matrix to cover the 'client built only through get_aws_client' clause of AC#1/#2.
- Open follow-up for the human: Organizations raises AccountNotFoundException (DescribeAccount) and TargetNotFoundException (ListTagsForResource); neither is in AWSSettings.NOT_FOUND_CODES, so they propagate as raw ClientError instead of NOT_FOUND. Not changed here because the plan scopes settings.py out.
- Gates: ruff clean; mypy clean on packages/aws_platform (remaining errors are pre-existing, outside this change); pytest tests --ignore=tests/smoke -> 3383 passed, 6 failed (pre-existing test-order leaks in test_webhooks_aws_sns.py and directory/test_google.py; they pass in isolation).

Human decision 2026-09-14 (option B, beyond the plan's 'no settings.py changes'): added AccountNotFoundException and TargetNotFoundException to AWSSettings.NOT_FOUND_CODES defaults in integrations/aws/settings.py, so Organizations not-found errors classify as NOT_FOUND instead of propagating as a raw ClientError. Both codes are Organizations-only, so other classify_aws_error users (identitystore, DynamoDB, Shield, access sync) are unaffected, and no AWS_NOT_FOUND_CODES override exists outside tests. No production effect until the caller migrations land. Covered by two new parametrized cases in tests/unit/integrations/aws/test_aws_client_classify_error.py (seen failing first). Gates after the change: ruff clean; mypy 87 errors, unchanged and all outside this change; pytest tests --ignore=tests/smoke -> 3385 passed, 6 failed (the same order-dependent tests as before).
<!-- SECTION:NOTES:END -->
