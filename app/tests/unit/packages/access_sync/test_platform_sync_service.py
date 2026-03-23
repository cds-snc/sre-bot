"""Unit tests for PlatformSyncService bulk reconciliation behavior."""

from typing import Any, Dict, List, Optional, Set

import pytest

from infrastructure.directory.models import DirectoryGroup, DirectoryMember
from infrastructure.operations import OperationResult
from packages.access_sync.models import (
    MembershipContext,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access_sync.platform_sync.service import PlatformSyncService
from packages.access_sync.policies import (
    EntitlementRule,
    PlatformPolicy,
    PolicyRegistry,
)
from packages.access_sync.registry import AccessSyncRegistry


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

    def get_group_members(self, group_email: str) -> OperationResult:
        return OperationResult.success(data=self._members.get(group_email, []))


class FakeAdapter:
    """Adapter test double exposing bulk and fallback list interfaces."""

    def __init__(self) -> None:
        self.calls: List[str] = []

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
        context: MembershipContext,
        current_entitlement_ids: Optional[Set[str]] = None,
        platform_user_exists: Optional[bool] = None,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        self.calls.append(
            {
                "user_email": user_email,
                "platform": platform,
                "context": context,
                "current_entitlement_ids": current_entitlement_ids,
                "platform_user_exists": platform_user_exists,
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
        registry=AccessSyncRegistry(adapters={"aws": adapter_any}),
        policies=PolicyRegistry(policies={"aws": policy}),
        directory=directory_any,
    )

    result = platform_sync.sync_platform("aws", dry_run=True, run_id="run-1")

    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.users_synced == 3
    assert "list_members_for_groups" in adapter.calls

    calls_by_email = {call["user_email"]: call for call in sync_service.calls}

    assert calls_by_email["alice@example.com"]["current_entitlement_ids"] == {
        "group-admin"
    }
    assert calls_by_email["alice@example.com"]["platform_user_exists"] is True

    assert calls_by_email["bob@example.com"]["current_entitlement_ids"] == set()
    assert calls_by_email["bob@example.com"]["platform_user_exists"] is False

    assert calls_by_email["carol@example.com"]["current_entitlement_ids"] == {
        "group-admin"
    }
    assert calls_by_email["carol@example.com"]["platform_user_exists"] is True
