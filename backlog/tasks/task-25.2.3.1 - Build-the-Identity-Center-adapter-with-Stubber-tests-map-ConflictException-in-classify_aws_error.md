---
id: TASK-25.2.3.1
title: >-
  Build the Identity Center adapter with Stubber tests; map ConflictException in
  classify_aws_error
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-11 19:18'
updated_date: '2026-09-11 19:34'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.2
references:
  - app/integrations/aws/identity_store.py
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - app/packages/access/sync/adapters/aws_identity_center.py
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
parent_task_id: TASK-25.2.3
priority: high
ordinal: 192000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 (expand) of TASK-25.2.3, split 2026-09-11 under the single-PR size gate (the combined task estimated ~12 production files mixing new code, a behaviour-changing caller migration and a deletion). Nothing consumes the adapter yet; TASK-25.2.3.2 migrates the callers and deletes the legacy module.

Create packages/aws_platform/adapters/identity_center.py: IdentityCenterAdapter holds typed identitystore clients from get_aws_client("identitystore", role_arn=...), reads IdentityStoreId from AWSSettings.INSTANCE_ID, exposes the thirteen operations the legacy callers use (healthcheck, create_user, delete_user, get_user_id, describe_user, list_users, get_group_id, list_groups, create_group_membership, delete_group_membership, get_group_membership_id, list_group_memberships, list_groups_with_memberships), paginates through client.get_paginator, wraps each SDK call in try/except + classify_aws_error and returns OperationResult. build_identity_center_adapter() is the provider (mirrors packages/access's build_aws_identity_center_adapter; clients carry eagerly assumed credentials, so callers build the adapter at function entry, never at import time).

Human decisions 2026-09-11: create_user and create_group_membership use a retries=False client (no client token on those APIs); every other operation uses the standard-retry client. ConflictException (entity already exists, an expected sync outcome) is mapped to PERMANENT_ERROR in classify_aws_error next to ConditionalCheckFailedException. healthcheck means "a single-page ListUsers succeeds" (an empty store is healthy). The groups-with-memberships join keeps its legacy semantics (group filters, user details merged into MemberId, per-group membership failures logged and skipped, tolerate_errors kept); the filter step is a one-line comprehension inside the adapter rather than an import of utils.filters, because packages/ imports nothing from utils today.

packages/aws_platform is the provisional transition seam described in TASK-25.2 (dissolved by TASK-88): empty __init__.py files, no hookimpls, no entry-point, no settings.py, no business logic beyond the join the callers already need.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/aws_platform/adapters/identity_center.py defines IdentityCenterAdapter exposing healthcheck, create_user, delete_user, get_user_id, describe_user, list_users, get_group_id, list_groups, create_group_membership, delete_group_membership, get_group_membership_id, list_group_memberships and list_groups_with_memberships, each returning OperationResult; ClientError/BotoCoreError go through classify_aws_error and any other exception propagates
- [ ] #2 build_identity_center_adapter() constructs clients only through get_aws_client('identitystore', role_arn=SERVICE_ROLE_MAP['identitystore'] or None), reads IdentityStoreId from AWSSettings.INSTANCE_ID, and hands create_user and create_group_membership a retries=False client while every other operation uses the standard-retry client; no boto3 construction and no cast in the adapter
- [ ] #3 list_users, list_groups and list_group_memberships paginate through client.get_paginator; list_groups_with_memberships keeps the legacy join semantics (group filters applied, user details merged into MemberId, per-group membership failures logged and skipped, tolerate_errors preserved) and returns a failed list_groups or list_users as its own failure result
- [ ] #4 healthcheck returns a success result iff a single-page list_users call (MaxResults=1) succeeds
- [ ] #5 classify_aws_error maps ConflictException to PERMANENT_ERROR, covered by a test alongside the existing mapped families in tests/unit/integrations/aws/test_aws_client_classify_error.py
- [ ] #6 botocore Stubber unit tests under tests/unit/packages/aws_platform/ cover each operation's success path with expected params (IdentityStoreId on every call), pagination across two pages, the join cases, and the classification paths NOT_FOUND, UNAUTHORIZED, transient with retry_after, ConflictException permanent, BotoCoreError transient and an unmapped ClientError propagating; provider tests assert which client each write uses
- [ ] #7 No production caller changes and integrations/aws/identity_store.py is untouched; ruff, mypy (no new errors) and pytest pass with output recorded; make check-sdk-typing and make check-vendor-package-contract pass with no baseline edits
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-11, re-grepped against current code after TASK-25.2.2 merged)
- Legacy surface being mirrored (app/integrations/aws/identity_store.py, 379 lines, all through execute_aws_api_call + @handle_aws_api_errors, role_arn=settings.ORG_ROLE_ARN, IdentityStoreId=settings.INSTANCE_ID): healthcheck :29 (list_users truthy); create_user :49 (UserName=email, Emails=[{Value,Type=WORK,Primary=True}], Name={GivenName,FamilyName}, DisplayName="first last" -> UserId); delete_user :74 (-> True); get_user_id :96 (AlternateIdentifier.UniqueAttribute AttributePath "userName" -> UserId); describe_user :118 (response minus ResponseMetadata/IdentityStoreId); list_users :138 (paginated, key Users, optional Filters); get_group_id :148 (AttributePath "displayName" -> GroupId); list_groups :174 (paginated, key Groups, optional Filters); create_group_membership :194 (GroupId, MemberId={UserId} -> MembershipId); delete_group_membership :217 (-> True); get_group_membership_id :239 (-> MembershipId); list_group_memberships :259 (paginated, key GroupMemberships); list_groups_with_memberships :285-379 (list_groups, filter groups by callables, project groups to GroupId/DisplayName/Description/IdentityStoreId, list_users once, per group list_group_memberships with failures logged+skipped, merge the matching user dict into membership["MemberId"], missing user -> warning and break unless tolerate_errors, keep groups with memberships only).
- Factory/classifier as shipped by 25.2.2: get_aws_client(service, *, role_arn=None, session_name="sre-bot", retries=True) client.py:138-161, identitystore overload :66-71, retries=False -> max_attempts 0 :166; classify_aws_error(exc) -> (OperationStatus, code, retry_after) client.py:196-221, re-raises unmapped codes at :221, ConditionalCheckFailedException hardcoded at :218. Settings: integrations/aws/settings.py get_aws_settings() :120 (lru_cache), INSTANCE_ID :101, SERVICE_ROLE_MAP :105-116 (identitystore -> ORG_ROLE_ARN), catalogues :56-93 (NOT_FOUND: ResourceNotFoundException...; UNAUTHORIZED: AccessDeniedException...; TRANSIENT: ThrottlingException... with TRANSIENT_RETRY_AFTER_SECONDS default 60).
- Pattern to mirror: packages/access/sync/adapters/aws_identity_center.py _map_sdk_exception/_call/_paginate :105-128 and build_aws_identity_center_adapter :1216-1226 (settings -> SERVICE_ROLE_MAP.get("identitystore") or None -> get_aws_client -> adapter). OperationResult: infrastructure/operations/result.py:21-277 (.success/.error, is_success); OperationStatus: status.py:10-25.
- Stubber precedent: tests/unit/integrations/aws/test_aws_client_assume_role.py:48-58 (real client + Stubber + expected_params + assert_no_pending_responses). Typed paginators exist in types_boto3_identitystore (client.pyi get_paginator overloads for list_users/list_groups/list_group_memberships), so no cast is needed.
- Layout: packages/<pkg>/__init__.py and adapters/__init__.py are empty (packages/incident/drive); tests/unit/packages/<pkg>/__init__.py exists per package. packages/ imports nothing from utils today (rg), so the group filter step is an inline comprehension, not utils.filters.
- Guards: bin/check_sdk_typing.py and bin/check_vendor_package_contract.py scan app/integrations only; a new module under packages/ cannot trip them and client.py stays baselined for execute_aws_api_call. mypy excludes tests/ and carries 87 pre-existing errors in untouched files (25.2.2 notes).
- Pre-flight (dev environment, no repo change): the container was rebuilt; before trusting local mypy run `cd app && uv sync --locked` and confirm `uv run python -c "import types_boto3_identitystore"` resolves, as 25.2.2 found a stray boto3-stubs shadowing types-boto3.

DESIGN DECISIONS (human, 2026-09-11)
- Two clients per adapter instance: standard-retry for reads/deletes/gets, retries=False for create_user and create_group_membership (no client token on those APIs).
- ConflictException -> PERMANENT_ERROR in classify_aws_error, hardcoded next to ConditionalCheckFailedException (not a settings catalogue).
- healthcheck = single-page ListUsers(MaxResults=1) succeeds; empty store is healthy.
- Provider is build_identity_center_adapter() in the adapter module; callers build at function entry (assumed credentials expire; nothing at import time).
- Return shapes stay dict-based (the callers consume raw Identity Store dicts through provisioning helpers); no domain dataclass is introduced in this seam (TASK-88 owns the eventual capability package).

SIZE ESTIMATE / GATE: 4 production files (packages/aws_platform/__init__.py 0 LOC, adapters/__init__.py 0 LOC, adapters/identity_center.py ~260 LOC, integrations/aws/client.py +2/-1) ~265 production LOC, one subsystem plus a two-line classifier edit; no caller changes. Under the single-PR gate. Tests ~450 LOC across three new files plus one case in an existing file.

STEPS
1. TDD first: write the failing tests (see TEST MATRIX) under tests/unit/packages/aws_platform/ (__init__.py empty) and the ConflictException case in tests/unit/integrations/aws/test_aws_client_classify_error.py next to test_conditional_check_failure_is_permanent. Run them; they fail on ImportError / unmapped propagation. (AC#5, AC#6)
2. app/integrations/aws/client.py:218: extend the permanent branch to `if code in ("ConditionalCheckFailedException", "ConflictException")`; docstring line notes Identity Store already-exists conflicts. Nothing else in client.py changes. (AC#5)
3. Create app/packages/aws_platform/__init__.py and app/packages/aws_platform/adapters/__init__.py, both empty (module docstring only), no hookimpl, no entry-point line in pyproject.toml. (AC#1)
4. Create app/packages/aws_platform/adapters/identity_center.py: (AC#1, AC#2, AC#3, AC#4)
   - Imports: structlog; botocore.exceptions ClientError, BotoCoreError; collections.abc Callable, Mapping; typing TYPE_CHECKING, Any; infrastructure.operations OperationResult, OperationStatus; integrations.aws.client classify_aws_error, get_aws_client; integrations.aws.settings get_aws_settings; under TYPE_CHECKING: types_boto3_identitystore.client.IdentityStoreClient.
   - class IdentityCenterAdapter.__init__(self, identitystore: IdentityStoreClient, identitystore_no_retry: IdentityStoreClient, identity_store_id: str).
   - Helpers: _map_sdk_exception(exc) -> OperationResult.error(status, message=str(exc), error_code=..., retry_after=..., provider="aws", operation=name); _call(operation, fn) catching (ClientError, BotoCoreError) only; _paginate(operation, paginator_name, response_key, **kwargs) using self._identitystore.get_paginator(...) and flattening pages. Every other exception propagates.
   - Operations, all keyword `IdentityStoreId=self._identity_store_id`: healthcheck() -> list_users(MaxResults=1) -> success(data=True); create_user(email, first_name, family_name) on the no-retry client, same payload as legacy :62-68, data=UserId; delete_user(user_id) data=True; get_user_id(user_name) AlternateIdentifier userName, data=UserId; describe_user(user_id) data=dict without ResponseMetadata/IdentityStoreId; list_users(filters=None) paginated Users (Filters only when given); get_group_id(group_name) AlternateIdentifier displayName, data=GroupId; list_groups(filters=None) paginated Groups; create_group_membership(group_id, user_id) on the no-retry client, data=MembershipId; delete_group_membership(membership_id) data=True; get_group_membership_id(group_id, user_id) data=MembershipId; list_group_memberships(group_id) paginated GroupMemberships.
   - list_groups_with_memberships(groups_filters: list[Callable[[dict], bool]] | None = None, tolerate_errors: bool = False) -> OperationResult[list[dict]]: groups = self.list_groups(); non-success -> return it; empty -> success([]); apply each filter with a comprehension; project the four keys; users = self.list_users(); non-success -> return it; index users by UserId once (dict) instead of the legacy linear `next(...)`, same merge result; per group: memberships = self.list_group_memberships(group_id); non-success -> log error with status/error_code and skip the group (legacy: logged + continue); merge user details into membership["MemberId"]; missing user -> warning, error_occurred=True, break unless tolerate_errors; keep group only if memberships and (not error_occurred or tolerate_errors); return success(data=groups_with_memberships). Same structured log event names as legacy (aws_identity_store_*), so dashboards keep working.
   - build_identity_center_adapter() -> IdentityCenterAdapter: settings = get_aws_settings(); role_arn = settings.SERVICE_ROLE_MAP.get("identitystore") or None; two get_aws_client("identitystore", role_arn=role_arn) calls, the second with retries=False; IdentityStoreId=settings.INSTANCE_ID.
5. Verification gates from app/: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` (zero errors in the new files; pre-existing count unchanged), `uv run pytest tests/unit/packages/aws_platform tests/unit/integrations/aws -q`, then the full `uv run pytest tests --ignore=tests/smoke`, `make check-sdk-typing`, `make check-vendor-package-contract`. Record outputs in notes. (AC#7)
6. Notes: record that no caller was migrated, that identity_store.py is untouched, and the one classifier behaviour change (ConflictException now PERMANENT_ERROR for every classify_aws_error caller) for review.

TEST MATRIX (file names per testing-standards; docstrings describe behaviour and stub strategy only)
- tests/unit/packages/aws_platform/test_aws_platform_identity_center_operations.py — fixture builds a real boto3 identitystore client with dummy static credentials + region, wraps it in Stubber, and constructs IdentityCenterAdapter(client, client, "d-1234567890"). Per operation: success path with expected_params including IdentityStoreId and the exact legacy payload (create_user Emails/Name/DisplayName; get_user_id AttributePath userName; get_group_id AttributePath displayName; healthcheck MaxResults=1) and the data shape asserted (UserId / GroupId / MembershipId / True / stripped describe_user dict). Boundary: list_users, list_groups and list_group_memberships flatten two pages (NextToken) and pass Filters only when provided; healthcheck succeeds on an empty Users page. Failure/classification (add_client_error on one representative operation each, codes from the default catalogues): ResourceNotFoundException -> NOT_FOUND with error_code; AccessDeniedException -> UNAUTHORIZED; ThrottlingException -> TRANSIENT_ERROR with retry_after 60; ConflictException on create_user and create_group_membership -> PERMANENT_ERROR; BotoCoreError (monkeypatch the client method to raise botocore.exceptions.EndpointConnectionError) -> TRANSIENT_ERROR; ValidationException (unmapped) propagates as ClientError; a programmer error (KeyError from a monkeypatched method) propagates. Every test ends with assert_no_pending_responses.
- tests/unit/packages/aws_platform/test_aws_platform_identity_center_groups_join.py — list_groups_with_memberships through Stubber: groups filtered by a callable; projection to the four keys; user details merged into MemberId; a group whose list_group_memberships fails is skipped while the rest are returned; a membership whose user is absent drops the group when tolerate_errors=False and keeps it when True; empty groups -> success([]); failed list_groups -> that failure result, no further calls; failed list_users -> that failure result.
- tests/unit/packages/aws_platform/test_aws_platform_identity_center_provider.py — monkeypatch integrations.aws.client.get_aws_client through the adapter module namespace with a recorder: asserts exactly two calls, both service "identitystore" with role_arn from SERVICE_ROLE_MAP["identitystore"] (set via AWS_ORG_ACCOUNT_ROLE_ARN env + cache_clear), the second with retries=False, and None role_arn when the setting is empty; asserts IdentityStoreId from AWS_SSO_INSTANCE_ID; write routing: two Stubbers, create_user/create_group_membership responses registered only on the no-retry stub and get_user_id only on the standard stub, both assert_no_pending_responses.
- tests/unit/integrations/aws/test_aws_client_classify_error.py — test_conflict_is_permanent: ConflictException -> (PERMANENT_ERROR, "ConflictException", None).

AC TRACEABILITY: AC#1 -> steps 3-4, operations file; AC#2 -> step 4 provider, provider file; AC#3 -> step 4 paginate/join, operations + groups_join files; AC#4 -> step 4 healthcheck, operations file; AC#5 -> step 2, classify test; AC#6 -> step 1, all three files; AC#7 -> step 5.

ASSUMPTIONS AND DOUBTS (verify during implementation)
- Stubber validates params against the identitystore service model, so MaxResults=1 on ListUsers and the AlternateIdentifier shapes must be model-valid; if Stubber rejects a legacy payload, the legacy payload was already wrong and the adapter follows the model (record in notes).
- types-boto3 identitystore get_paginator returns typed paginators whose page TypedDicts satisfy mypy without cast; verify with `uv run mypy app/packages/aws_platform`. Fallback is annotating the page loop with Mapping[str, Any], never cast.
- The legacy ORG_ROLE_ARN was passed even when empty ("" -> assume_role_session skipped it); SERVICE_ROLE_MAP.get(...) or None reproduces that, as packages/access already does.
- ConflictException mapping also changes packages/access's adapter (a raised conflict becomes a PERMANENT_ERROR result on ensure_user) and the DynamoDB stores (DynamoDB does not emit ConflictException, so no effect); the access feature is not enabled, noted for review only.
- Devcontainer venv state after the rebuild may again shadow types-boto3; pre-flight above.

BLAST RADIUS AND ROLLBACK: additive; no production caller imports the new package, so runtime behaviour is unchanged except the classifier mapping above. A single git revert of the PR restores the previous state. No config, env or manifest prerequisite. Ordering: 25.2.3.2 must not start until this merges.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-11 tests-first checkpoint (no production code changed). Added under app/tests/unit/packages/aws_platform/ (new __init__.py): test_aws_platform_identity_center_operations.py (27 tests: every operation's success path with Stubber expected_params incl. IdentityStoreId, two-page pagination for list_users/list_groups/list_group_memberships, Filters only when given, healthcheck MaxResults=1 on empty and non-empty pages, classification NOT_FOUND/UNAUTHORIZED/transient retry_after 60/ConflictException permanent on both creates/BotoCoreError transient, unmapped ValidationException and a KeyError propagating), test_aws_platform_identity_center_groups_join.py (10 tests: filters, four-key projection, user merge into MemberId, failed group skipped while the rest survive, missing user drop/keep by tolerate_errors, empty groups, failed list_groups/list_users returned as the failure), test_aws_platform_identity_center_provider.py (7 tests: two get_aws_client calls with the second retries=False, role_arn from AWS_ORG_ACCOUNT_ROLE_ARN or None when empty, IdentityStoreId from AWS_SSO_INSTANCE_ID proven on the wire, create_user/create_group_membership routed to the no-retry stub, get_user_id to the standard stub). Added test_conflict_is_permanent to tests/unit/integrations/aws/test_aws_client_classify_error.py.
Evidence: `uv run ruff check` and `ruff format --check` clean on the new files. `uv run pytest tests/unit/packages/aws_platform tests/unit/integrations/aws/test_aws_client_classify_error.py -q` -> 3 collection errors (ModuleNotFoundError: packages.aws_platform) and test_conflict_is_permanent failing on the re-raised ClientError; `uv run pytest tests/unit/integrations/aws -q` -> 1 failed (that case), 132 passed. Review notes on the generated tests: replaced a lambda-patched paginator with real two-page Stubber responses, removed `from __future__ import annotations` from the new files (deprecated on 3.14), made the provider store-id test assert the request rather than a private attribute, and gave the skipped-group join test a surviving group so it proves selective skipping. Full suite deliberately not run at this checkpoint.
<!-- SECTION:NOTES:END -->
