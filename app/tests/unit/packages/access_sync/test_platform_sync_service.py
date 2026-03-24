"""Unit tests for PlatformSyncService bulk reconciliation behavior."""

from typing import Any, Dict, List, cast, Set

import pytest

from infrastructure.directory.models import DirectoryGroup, DirectoryMember
from infrastructure.operations import OperationResult
from packages.access_sync.models import (
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access_sync.platform_sync.service import PlatformSyncService
from packages.access_sync.policies import (
    AdapterCapabilities,
    EntitlementRule,
    PlatformPolicy,
)


class FakeDirectoryProvider:
    """Directory provider test double with static group/member fixtures."""

    def __init__(self) -> None:
        self._groups = {
            "sg-aws-authn": DirectoryGroup(
                group_email="sg-aws-authn@example.com",
                group_slug="sg-aws-authn",
                provider_group_id="gid-authn",
            ),
            "sg-aws-admin": DirectoryGroup(
                group_email="sg-aws-admin@example.com",
                group_slug="sg-aws-admin",
                provider_group_id="gid-admin",
            ),
        }
        self._members = {
            "sg-aws-authn@example.com": [
                DirectoryMember(email="alice@example.com"),
                DirectoryMember(email="bob@example.com"),
            ],
            "sg-aws-admin@example.com": [
                DirectoryMember(email="bob@example.com"),
            ],
        }

    def get_group(self, slug: str) -> OperationResult:
        return OperationResult.success(data=self._groups.get(slug))

    def get_group_members(
        self,
        group_email: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult:
        return OperationResult.success(data=self._members.get(group_email, []))


class FakeAdapter:
    """Adapter test double exposing bulk and fallback list interfaces."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=False,
            supports_delete=True,
            supported_entitlement_types={"group"},
            supports_bulk_user_delta=True,
        )

    def list_all_provisioned_users(self) -> OperationResult:
        self.calls.append("list_all_provisioned_users")
        return OperationResult.success(data={"alice@example.com", "carol@example.com"})

    def list_members_for_groups(self, group_ids: Set[str]) -> OperationResult:
        self.calls.append("list_members_for_groups")
        assert group_ids == {"group-admin"}
        return OperationResult.success(
            data={"group-admin": {"alice@example.com", "carol@example.com"}}
        )


class FakeUserSyncService:
    """UserSyncService test double to capture sync_user_from_context invocations."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, object]] = []

    def sync_user_from_context(
        self,
        user_email: str,
        platform: str,
        desired_state: DesiredUserState,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        self.calls.append(
            {
                "user_email": user_email,
                "platform": platform,
                "desired_state": desired_state,
                "dry_run": dry_run,
                "request_id": request_id,
            }
        )
        return OperationResult.success(
            data=SyncOutcome(planned_actions=[], applied_actions=[])
        )


@pytest.mark.unit
def test_sync_platform_prefetches_current_entitlements_from_group_memberships() -> None:
    """Platform sync should pass precomputed current IDs into per-user convergence."""
    rule = EntitlementRule(
        group_slug="sg-aws-admin",
        entitlement_type="group",
        entitlement_id="group-admin",
        mode="sync_managed",
    )
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[rule],
    )

    adapter = FakeAdapter()
    sync_service = FakeUserSyncService()
    adapter_any: Any = adapter
    sync_service_any: Any = sync_service
    directory_any: Any = FakeDirectoryProvider()
    platform_sync = PlatformSyncService(
        sync_service=sync_service_any,
        adapters={"aws": adapter_any},
        policies={"aws": policy},
        directory=directory_any,
    )

    result = platform_sync.sync_platform("aws", dry_run=True, run_id="run-1")

    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.users_synced == 3
    assert "list_members_for_groups" in adapter.calls

    calls_by_email = {call["user_email"]: call for call in sync_service.calls}

    alice_state: DesiredUserState = cast(
        DesiredUserState,
        calls_by_email["alice@example.com"]["desired_state"],
    )
    bob_state: DesiredUserState = cast(
        DesiredUserState,
        calls_by_email["bob@example.com"]["desired_state"],
    )
    carol_state: DesiredUserState = cast(
        DesiredUserState,
        calls_by_email["carol@example.com"]["desired_state"],
    )

    assert alice_state.current_entitlement_ids == {"group-admin"}
    assert alice_state.platform_user_exists is True

    assert bob_state.current_entitlement_ids is None
    assert bob_state.platform_user_exists is False

    assert carol_state.current_entitlement_ids == {"group-admin"}
    assert carol_state.platform_user_exists is True


@pytest.mark.unit
def test_sync_platform_lifecycle_only_processes_delta_users_only() -> None:
    """Lifecycle-only policies should process add/remove delta users only."""
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
    )

    adapter = FakeAdapter()
    sync_service = FakeUserSyncService()
    adapter_any: Any = adapter
    sync_service_any: Any = sync_service
    directory_any: Any = FakeDirectoryProvider()
    platform_sync = PlatformSyncService(
        sync_service=sync_service_any,
        adapters={"aws": adapter_any},
        policies={"aws": policy},
        directory=directory_any,
    )

    result = platform_sync.sync_platform("aws", dry_run=True, run_id="run-2")

    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.users_synced == 2
    synced_emails = {str(call["user_email"]) for call in sync_service.calls}
    assert synced_emails == {"bob@example.com", "carol@example.com"}
    assert "list_members_for_groups" not in adapter.calls
