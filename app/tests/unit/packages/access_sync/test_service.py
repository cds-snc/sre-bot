"""Unit tests for AccessSyncService."""

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    DirectoryUser,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.policies import (
    AdapterCapabilities,
    EntitlementRule,
    PlatformPolicy,
    PolicyRegistry,
)
from packages.access_sync.registry import AccessSyncRegistry
from packages.access_sync.service import AccessSyncService
from packages.access_sync.store import InMemorySyncRunStore


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Minimal test double for an access sync adapter."""

    def __init__(self, user_should_exist: bool = True) -> None:
        self._user_should_exist = user_should_exist
        self.calls: list = []

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=False,
            supports_delete=True,
            supported_entitlement_types={"permission_set"},
        )

    def get_user(self, user_email: str) -> OperationResult:
        self.calls.append(("get_user", user_email))
        if self._user_should_exist:
            return OperationResult.success(data={"user_id": f"id-{user_email}"})
        return OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="User not found",
            error_code="USER_NOT_FOUND",
        )

    def ensure_user(self, user_email: str) -> OperationResult:
        self.calls.append(("ensure_user", user_email))
        return OperationResult.success(data={"user_id": f"id-{user_email}"})

    def disable_user(self, user_email: str) -> OperationResult:
        self.calls.append(("disable_user", user_email))
        return OperationResult.success(message="disabled")

    def remove_user(self, user_email: str) -> OperationResult:
        self.calls.append(("remove_user", user_email))
        return OperationResult.success(message="removed")

    def apply_entitlement(
        self, user_email: str, entitlement_type: str, entitlement_id: str
    ) -> OperationResult:
        self.calls.append(
            ("apply_entitlement", user_email, entitlement_type, entitlement_id)
        )
        return OperationResult.success(message="applied")

    def remove_entitlement(
        self, user_email: str, entitlement_type: str, entitlement_id: str
    ) -> OperationResult:
        self.calls.append(
            ("remove_entitlement", user_email, entitlement_type, entitlement_id)
        )
        return OperationResult.success(message="removed")

    def fetch_current_state(self, user_email: str) -> OperationResult:
        return OperationResult.success(
            data={"user_id": f"id-{user_email}", "assignments": []}
        )


class FakeDirectoryProvider:
    """Minimal directory provider stub for service tests."""

    def __init__(self, is_member: bool = True) -> None:
        self._is_member = is_member

    def warmup(self) -> OperationResult:
        return OperationResult.success()

    def health_check(self) -> OperationResult:
        return OperationResult.success()

    def get_user(self, email: str) -> OperationResult:
        return OperationResult.success(
            data=DirectoryUser(
                email=email,
                provider_user_id=f"uid-{email}",
                provider="fake",
            )
        )

    def list_users(self, query: str = "", limit: int = 100) -> OperationResult:
        return OperationResult.success(data=[])

    def get_group(self, group_key: str) -> OperationResult:
        normalized_group_key = group_key.strip().lower()
        if "@" not in normalized_group_key:
            normalized_group_key = f"{normalized_group_key}@example.com"
        group = DirectoryGroup(
            group_email=normalized_group_key,
            group_slug=normalized_group_key.split("@")[0],
            provider_group_id=f"gid-{normalized_group_key}",
        )
        return OperationResult.success(data=group)

    def list_groups(self, query: str) -> OperationResult:
        group = DirectoryGroup(
            group_email=f"{query}@example.com",
            group_slug=query,
            provider_group_id=f"gid-{query}",
        )
        return OperationResult.success(data=[group])

    def get_group_members(self, group_key: str) -> OperationResult:
        return OperationResult.success(data=[])

    def add_group_member(
        self,
        group_key: str,
        user_email: str,
        role: str = "MEMBER",
    ) -> OperationResult:
        return OperationResult.success(
            data=DirectoryMember(
                email=user_email,
                role=role,
                provider="fake",
            )
        )

    def remove_group_member(self, group_key: str, user_email: str) -> OperationResult:
        return OperationResult.success()

    def check_membership(self, group_key: str, user_email: str) -> OperationResult:
        result = MembershipCheckResult(
            group_email=group_key,
            group_slug=group_key.split("@")[0],
            provider_group_id=None,
            user_email=user_email,
            is_member=self._is_member,
        )
        return OperationResult.success(data=result)


def make_service(
    is_member: bool = True,
    platform: str = "aws",
    rules=None,
    authn_removal_mode: str = "delete",
) -> tuple:
    """Return (service, adapter, store) triple for a minimal test setup."""
    adapter = FakeAdapter()
    policy = PlatformPolicy(
        platform=platform,
        authn_group_slug=f"sg-{platform}-authn",
        authn_mode="derived",
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )
    registry = AccessSyncRegistry(adapters={platform: adapter})
    policies = PolicyRegistry(policies={platform: policy})
    directory = FakeDirectoryProvider(is_member=is_member)
    store = InMemorySyncRunStore()
    service = AccessSyncService(
        registry=registry,
        policies=policies,
        directory=directory,
        store=store,
    )
    return service, adapter, store


# ---------------------------------------------------------------------------
# compute_desired_state
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_desired_state_member_returns_true():
    # Arrange
    service, _, _ = make_service(is_member=True)

    # Act
    result = service.compute_desired_state(
        user_email="alice@example.com", platform="aws"
    )

    # Assert
    assert result.is_success
    assert result.data is True


@pytest.mark.unit
def test_compute_desired_state_non_member_returns_false():
    # Arrange
    service, _, _ = make_service(is_member=False)

    # Act
    result = service.compute_desired_state(user_email="bob@example.com", platform="aws")

    # Assert
    assert result.is_success
    assert result.data is False


@pytest.mark.unit
def test_compute_desired_state_unknown_platform_returns_error():
    # Arrange
    service, _, _ = make_service()

    # Act
    result = service.compute_desired_state(
        user_email="alice@example.com", platform="unknown"
    )

    # Assert
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"


# ---------------------------------------------------------------------------
# sync_user — user should exist
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_member_ensures_user():
    # Arrange
    service, adapter, store = make_service(is_member=True)

    # Act
    result = service.sync_user(user_email="alice@example.com", platform="aws")

    # Assert
    assert result.is_success
    assert "ensure_user" in result.applied_actions
    ensure_calls = [c for c in adapter.calls if c[0] == "ensure_user"]
    assert len(ensure_calls) == 1


@pytest.mark.unit
def test_sync_user_applies_sync_managed_entitlements():
    # Arrange
    rule = EntitlementRule(
        group_slug="sg-aws-admin",
        entitlement_type="permission_set",
        entitlement_id="123456789012/AWSAdministratorAccess",
        mode="sync_managed",
    )
    service, adapter, store = make_service(is_member=True, rules=[rule])

    # Act
    result = service.sync_user(user_email="alice@example.com", platform="aws")

    # Assert
    assert result.is_success
    assert "apply_entitlement" in result.applied_actions
    ent_calls = [c for c in adapter.calls if c[0] == "apply_entitlement"]
    assert any(c[3] == "123456789012/AWSAdministratorAccess" for c in ent_calls)


@pytest.mark.unit
def test_sync_user_skips_ephemeral_entitlements():
    # Arrange — ephemeral rule should never be in sync_managed_rules()
    rule = EntitlementRule(
        group_slug="sg-aws-privileged",
        entitlement_type="permission_set",
        entitlement_id="123/PrivilegedAccess",
        mode="ephemeral",
    )
    service, adapter, store = make_service(is_member=True, rules=[rule])

    # Act
    result = service.sync_user(user_email="alice@example.com", platform="aws")

    # Assert
    assert result.is_success
    ent_calls = [c for c in adapter.calls if c[0] == "apply_entitlement"]
    assert not ent_calls  # no entitlement applied


@pytest.mark.unit
def test_sync_user_skips_deactivated_entitlements():
    # Arrange — deactivated rule must not trigger any entitlement action
    rule = EntitlementRule(
        group_slug="sg-aws-legacy",
        entitlement_type="permission_set",
        entitlement_id="999/LegacyAccess",
        mode="deactivated",
    )
    service, adapter, store = make_service(is_member=True, rules=[rule])

    # Act
    result = service.sync_user(user_email="alice@example.com", platform="aws")

    # Assert
    assert result.is_success
    ent_calls = [c for c in adapter.calls if c[0] == "apply_entitlement"]
    assert not ent_calls


# ---------------------------------------------------------------------------
# sync_user — user should not exist
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_non_member_removes_user():
    # Arrange
    service, adapter, store = make_service(is_member=False, authn_removal_mode="delete")

    # Act
    result = service.sync_user(user_email="bob@example.com", platform="aws")

    # Assert
    assert result.is_success
    assert "remove_user" in result.applied_actions
    remove_calls = [c for c in adapter.calls if c[0] == "remove_user"]
    assert len(remove_calls) == 1


# ---------------------------------------------------------------------------
# sync_user — dry run
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_dry_run_returns_planned_actions_without_execution():
    # Arrange
    service, adapter, store = make_service(is_member=True)

    # Act
    result = service.sync_user(
        user_email="alice@example.com",
        platform="aws",
        dry_run=True,
    )

    # Assert
    assert result.is_success
    assert "ensure_user" in result.applied_actions
    assert not adapter.calls  # nothing executed


# ---------------------------------------------------------------------------
# sync_user — run record persistence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_persists_run_record():
    # Arrange
    service, _, store = make_service(is_member=True)

    # Act
    service.sync_user(
        user_email="alice@example.com", platform="aws", request_id="req-42"
    )

    # Assert
    runs = store.get_recent_runs(platform="aws", user_email="alice@example.com")
    assert len(runs) == 1
    assert runs[0].request_id == "req-42"
    assert runs[0].status == "success"


# ---------------------------------------------------------------------------
# sync_user — missing policy/adapter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_unknown_platform_returns_error():
    # Arrange
    service, _, _ = make_service()

    # Act
    result = service.sync_user(user_email="alice@example.com", platform="gcp")

    # Assert
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"
