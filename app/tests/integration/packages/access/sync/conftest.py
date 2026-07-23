"""Fixtures for access_sync integration tests.

Provides three layers of shared test infrastructure:

1. **Shared test doubles** — ``FakeDirectory`` and ``SpyAdapter`` are
   lightweight implementations of the directory provider and platform adapter
   protocols.  They give full control over IDP and platform state without
   touching real APIs.

2. **Factory fixtures** — ``make_sync_config`` and ``make_coordinator`` build
   configured coordinator stacks with safe defaults.  Tests override only the
   parameters relevant to the scenario being verified.

3. **AWS-specific helpers** — ``aws_config`` and ``make_adapter`` remain for
   the existing adapter group-mapping integration tests.

Separation of concerns between ``FakeDirectory`` fields:

    discovered_slugs
        Returned by ``list_groups(query=prefix)`` and ``list_groups("")``.
        Controls which groups the coordinator considers when building the
        effective policy.  Typically the platform-prefixed groups only.

    transitive_membership_slugs
        Controls what ``check_membership(group_email, user_email)`` returns.
        A slug in this set makes the membership check return ``True`` for
        *any* user.  Use it to model transitive (indirect) membership such as
        ``sg-aws-authn`` when the user is only a direct member of a subgroup.

    user_direct_group_slugs
        Returned by ``get_user_groups(user_email)``.  These are the *direct*
        group memberships that drive required-entitlement resolution.  Should
        *not* include the authn group itself when modelling transitive access.

    group_members
        Dict[slug, list[email]] used by ``get_group_members`` during
        ``sync_platform`` batch IDP reads (Phase 1).
"""

from typing import Any, Literal
from unittest.mock import MagicMock

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.common.config import PlatformPolicy
from packages.access.sync.adapters.aws_identity_center import AwsIdentityCenterAdapter
from packages.access.sync.application import AccessSyncApplicationService
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import (
    AdapterAssessment,
    DesiredPlatformState,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.sync.policies import (
    AdapterCapabilities,
    PlannedAction,
    PlanningContext,
    PlatformReconciliationPlanner,
    PolicyEngine,
)

# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------

_ACCESS_SYNC_ENV_KEYS = [
    "ACCESS_SYNC_ENABLED",
    "ACCESS_SYNC_RECONCILIATION_ENABLED",
    "ACCESS_SYNC_JOB_TTL_SECONDS",
    "ACCESS_CONFIG_SOURCE",
    "ACCESS_CONFIG_REF",
    "ACCESS_CONFIG_ENV_DIR_PREFIX",
    "ACCESS_CONFIG_ENV_DIR_SEPARATOR",
    "ACCESS_CONFIG_ENV_PLATFORMS_JSON",
]


@pytest.fixture(autouse=True)
def _access_sync_env_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all ACCESS_SYNC_* env vars before every integration test."""
    for key in _ACCESS_SYNC_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# FakeDirectory — IDP test double
# ---------------------------------------------------------------------------


class FakeDirectory:
    """Configurable IDP test double for integration tests.

    All methods return ``OperationResult`` to satisfy the ``DirectoryProvider``
    protocol used by ``DirectoryMembershipBuilder``.
    """

    def __init__(
        self,
        discovered_slugs: set[str] | None = None,
        transitive_membership_slugs: set[str] | None = None,
        user_direct_group_slugs: set[str] | None = None,
        group_members: dict[str, list[str]] | None = None,
    ) -> None:
        self._discovered: set[str] = discovered_slugs or set()
        self._transitive: set[str] = transitive_membership_slugs or set()
        self._direct: set[str] = user_direct_group_slugs or set()
        self._members: dict[str, list[str]] = group_members or {}

    def _make_group(self, slug: str) -> DirectoryGroup:
        return DirectoryGroup(
            group_email=f"{slug}@example.com",
            group_slug=slug,
            provider_group_id=f"gid-{slug}",
        )

    def get_group(self, slug: str) -> OperationResult:
        # Groups always exist in the IDP directory; only membership is configurable.
        # The membership question is answered by check_membership / get_user_groups.
        return OperationResult.success(data=self._make_group(slug))

    def check_membership(self, group_email: str, user_email: str) -> OperationResult:
        slug = group_email.split("@")[0]
        is_member = slug in self._transitive
        return OperationResult.success(
            data=MembershipCheckResult(
                group_email=group_email,
                group_slug=slug,
                provider_group_id=f"gid-{slug}",
                user_email=user_email,
                is_member=is_member,
            )
        )

    def get_user_groups(self, user_email: str) -> OperationResult:
        return OperationResult.success(data=[self._make_group(slug) for slug in self._direct])

    def get_group_members(
        self,
        group_email: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult:
        slug = group_email.split("@")[0]
        emails = self._members.get(slug, [])
        return OperationResult.success(data=[DirectoryMember(email=email) for email in emails])

    def get_group_members_batch(
        self,
        group_emails: list[str],
        include_member_types: set[str] | None = None,
    ) -> OperationResult:
        result = {}
        for group_email in group_emails:
            slug = group_email.split("@")[0]
            emails = self._members.get(slug, [])
            result[group_email] = [DirectoryMember(email=email) for email in emails]
        return OperationResult.success(data=result)

    def list_groups(self, query: str = "") -> OperationResult:
        matching = [self._make_group(slug) for slug in self._discovered if not query or slug.startswith(query)]
        return OperationResult.success(data=matching)


# ---------------------------------------------------------------------------
# SpyAdapter — platform adapter test double
# ---------------------------------------------------------------------------


class SpyAdapter:
    """In-memory platform adapter that records reconcile calls.

    Configurable return values let individual tests control current platform
    state without wiring real API clients. Implements the AccessSyncAdapter
    protocol with reconcile_user() and reconcile_platform().
    """

    def __init__(
        self,
        current_entitlement_ids: set[str] | None = None,
        user_exists: bool = True,
        provisioned_users: set[str] | None = None,
        supports_disable: bool = False,
        group_members: dict[str, set[str]] | None = None,
    ) -> None:
        self.calls: list[tuple] = []
        self._current_ids: set[str] = current_entitlement_ids if current_entitlement_ids is not None else set()
        self._user_exists = user_exists
        self._provisioned = provisioned_users
        self._supports_disable = supports_disable
        self._group_members: dict[str, set[str]] = group_members or {}

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=self._supports_disable,
            supports_delete=True,
            supported_entitlement_types={"group"},
            supports_bulk_user_delta=True,
        )

    def ensure_user(self, email: str) -> OperationResult:
        self.calls.append(("ensure_user", email))
        return OperationResult.success()

    def disable_user(self, email: str) -> OperationResult:
        self.calls.append(("disable_user", email))
        return OperationResult.success()

    def remove_user(self, email: str) -> OperationResult:
        self.calls.append(("remove_user", email))
        return OperationResult.success()

    def apply_entitlement(self, email: str, etype: str, eid: str) -> OperationResult:
        self.calls.append(("apply_entitlement", email, etype, eid))
        return OperationResult.success()

    def remove_entitlement(self, email: str, etype: str, eid: str) -> OperationResult:
        self.calls.append(("remove_entitlement", email, etype, eid))
        return OperationResult.success()

    def _get_assessment(self, email: str) -> AdapterAssessment:
        if not self._user_exists:
            return AdapterAssessment(
                platform_user_exists=False,
                current_entitlement_ids=set(),
            )
        return AdapterAssessment(
            platform_user_exists=True,
            current_entitlement_ids=set(self._current_ids),
        )

    def reconcile_user(
        self,
        user_email: str,
        desired_state: DesiredUserState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        self.calls.append(("reconcile_user", user_email))
        current = self._get_assessment(user_email)
        engine = PolicyEngine()
        planned = engine.plan_actions(
            policy=context,
            capabilities=self.capabilities(),
            user_should_exist=desired_state.user_should_exist,
            required_entitlements=desired_state.required_entitlements,
            current_entitlement_ids=current.current_entitlement_ids,
            platform_user_exists=current.platform_user_exists,
        )
        applied: list[str] = []
        if not dry_run:
            for action in planned:
                if action.action == "provision_user":
                    self.ensure_user(user_email)
                    applied.append(action.action)
                elif action.action == "disable_user":
                    self.disable_user(user_email)
                    applied.append(action.action)
                elif action.action == "remove_user":
                    self.remove_user(user_email)
                    applied.append(action.action)
                elif action.action == "apply_entitlement" and action.entitlement_type and action.entitlement_id:
                    self.apply_entitlement(user_email, action.entitlement_type, action.entitlement_id)
                    applied.append(action.action)
                elif action.action == "remove_entitlement" and action.entitlement_type and action.entitlement_id:
                    self.remove_entitlement(user_email, action.entitlement_type, action.entitlement_id)
                    applied.append(action.action)
        return OperationResult.success(
            data=SyncOutcome(
                planned_actions=[a.action for a in planned],
                applied_actions=applied,
            )
        )

    def reconcile_platform(  # noqa: C901
        self,
        desired_state: DesiredPlatformState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        self.calls.append(("reconcile_platform",))
        planner = PlatformReconciliationPlanner()
        current_users = self._provisioned if self._provisioned is not None else set()
        plan = planner.plan_platform_actions(
            desired_users=desired_state.desired_users,
            desired_members_by_entitlement=desired_state.desired_members_by_entitlement,
            current_users=current_users,
            current_members_by_entitlement=self._group_members,
            authn_removal_mode=context.authn_removal_mode,
        )
        actions_by_user: dict[str, list[PlannedAction]] = {}
        for email in sorted(plan.users_to_provision):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="provision_user"))
        for entitlement_id, members in sorted(plan.entitlement_adds_by_id.items()):
            for email in sorted(members):
                actions_by_user.setdefault(email, []).append(
                    PlannedAction(
                        action="apply_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for entitlement_id, members in sorted(plan.entitlement_removes_by_id.items()):
            for email in sorted(members):
                actions_by_user.setdefault(email, []).append(
                    PlannedAction(
                        action="remove_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for email in sorted(plan.users_to_disable):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="disable_user"))
        for email in sorted(plan.users_to_remove):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="remove_user"))

        users_converged = 0
        per_user: dict[str, SyncOutcome] = {}
        for email, planned in sorted(actions_by_user.items()):
            applied: list[str] = []
            if not dry_run:
                for action in planned:
                    if action.action == "provision_user":
                        self.ensure_user(email)
                        applied.append(action.action)
                    elif action.action == "disable_user":
                        self.disable_user(email)
                        applied.append(action.action)
                    elif action.action == "remove_user":
                        self.remove_user(email)
                        applied.append(action.action)
                    elif action.action == "apply_entitlement" and action.entitlement_type and action.entitlement_id:
                        self.apply_entitlement(email, action.entitlement_type, action.entitlement_id)
                        applied.append(action.action)
                    elif action.action == "remove_entitlement" and action.entitlement_type and action.entitlement_id:
                        self.remove_entitlement(email, action.entitlement_type, action.entitlement_id)
                        applied.append(action.action)
            outcome = SyncOutcome(
                planned_actions=[a.action for a in planned],
                applied_actions=applied,
            )
            per_user[email] = outcome
            if applied:
                users_converged += 1
        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=context.platform,
                users_synced=len(desired_state.desired_users | current_users),
                users_converged=users_converged,
                orphans_found=len(current_users - desired_state.desired_users),
                requires_manual_action_count=0,
                dry_run=dry_run,
                per_user=per_user,
            )
        )


# ---------------------------------------------------------------------------
# Factory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_sync_config():
    """Factory for ``AccessSyncRuntimeConfig`` with safe production-like defaults.

    Default: single ``aws`` platform, ``sg`` dir_prefix, ``-`` separator.
    Override ``mode_overrides`` to exclude specific tokens from sync::

        config = make_sync_config(mode_overrides={"scratch": "ephemeral"})
    """

    def _make(
        platform: str = "aws",
        authn_token: str = "authn",
        authn_removal_mode: str = "delete",
        mode_overrides: dict[str, Literal["sync_managed", "ephemeral", "deactivated"]] | None = None,
        dir_prefix: str = "sg",
        dir_separator: str = "-",
        adapter_type: str = "fake",
    ) -> AccessSyncRuntimeConfig:
        return AccessSyncRuntimeConfig(
            dir_prefix=dir_prefix,
            dir_separator=dir_separator,
            platforms={
                platform: PlatformPolicy(
                    authn_token=authn_token,
                    authn_removal_mode=authn_removal_mode,
                    adapter_type=adapter_type,
                    mode_overrides=mode_overrides or {},
                )
            },
        )

    return _make


@pytest.fixture
def make_coordinator(make_sync_config):
    """Factory for a fully-wired ``AccessSyncApplicationService`` backed by test doubles.

    Returns ``(coordinator, adapter)`` so tests can assert on adapter call
    records after running a sync.

    IDP state is controlled through ``FakeDirectory`` parameters:

    * ``discovered_slugs`` — groups visible to ``list_groups``
    * ``transitive_membership_slugs`` — groups where ``check_membership``
      returns ``True`` (models transitive/indirect membership)
    * ``user_direct_group_slugs`` — groups returned by ``get_user_groups``
      (models direct group membership used for entitlement matching)
    * ``group_members`` — mapping for batch platform-sync IDP reads

    Platform state is controlled through ``SpyAdapter`` parameters::

        coordinator, adapter = make_coordinator(
            mode_overrides={"scratch": "ephemeral"},
            discovered_slugs={"sg-aws-scratch"},
            transitive_membership_slugs={"sg-aws-authn"},
            user_direct_group_slugs={"sg-aws-scratch"},
            user_exists=True,
        )
    """

    def _make(
        platform: str = "aws",
        authn_removal_mode: str = "delete",
        mode_overrides: dict[str, Literal["sync_managed", "ephemeral", "deactivated"]] | None = None,
        # IDP state
        discovered_slugs: set[str] | None = None,
        transitive_membership_slugs: set[str] | None = None,
        user_direct_group_slugs: set[str] | None = None,
        group_members: dict[str, list[str]] | None = None,
        # Platform adapter state
        current_entitlement_ids: set[str] | None = None,
        user_exists: bool = True,
        provisioned_users: set[str] | None = None,
        supports_disable: bool = False,
        adapter_group_members: dict[str, set[str]] | None = None,
    ) -> tuple:
        config = make_sync_config(
            platform=platform,
            authn_removal_mode=authn_removal_mode,
            mode_overrides=mode_overrides,
        )
        # Default transitive membership: authn slug is reachable (e.g. via a subgroup)
        authn_slug = config.authn_group_slug(platform)
        transitive = transitive_membership_slugs if transitive_membership_slugs is not None else {authn_slug}
        directory = FakeDirectory(
            discovered_slugs=discovered_slugs,
            transitive_membership_slugs=transitive,
            user_direct_group_slugs=user_direct_group_slugs,
            group_members=group_members,
        )
        adapter = SpyAdapter(
            current_entitlement_ids=current_entitlement_ids,
            user_exists=user_exists,
            provisioned_users=provisioned_users,
            supports_disable=supports_disable,
            group_members=adapter_group_members,
        )
        directory_provider: Any = directory
        coordinator = AccessSyncApplicationService(
            adapters={platform: adapter},
            config=config,
            membership_builder=DirectoryMembershipBuilder(directory_provider),
        )
        return coordinator, adapter

    return _make


# ---------------------------------------------------------------------------
# AWS-specific helpers (used by test_adapter_group_mapping.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_config() -> AccessSyncRuntimeConfig:
    """Canonical AccessSyncRuntimeConfig for AWS integration tests.

    Uses the same naming convention as production:
        dir_prefix="sg", dir_separator="-"
        → group prefix "sg-aws-", authn slug "sg-aws-authn"
    """
    return AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={
            "aws": PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
            ),
        },
    )


def make_adapter(
    aws_ic_groups: list[dict[str, Any]],
) -> tuple[AwsIdentityCenterAdapter, MagicMock]:
    """Build an adapter wired to a fake IdentityStore with a known group list.

    Returns ``(adapter, fake_identitystore)`` so callers can assert on mock
    call counts with the correct ``MagicMock`` type rather than piercing the
    adapter's private ``_aws`` attribute through a typed production facade.

    ``describe_group`` always returns NOT_FOUND (tokens are not UUIDs) so the
    adapter falls through to the name-based group index on every resolution.
    """
    fake_identitystore = MagicMock()
    fake_identitystore.describe_group.return_value = OperationResult.error(
        OperationStatus.NOT_FOUND,
        message="not a uuid",
        error_code="NOT_FOUND",
    )
    fake_identitystore.list_groups.return_value = OperationResult.success(data=aws_ic_groups)
    fake_aws = MagicMock()
    fake_aws.identitystore = fake_identitystore
    adapter = AwsIdentityCenterAdapter(aws_clients=fake_aws)
    return adapter, fake_identitystore
