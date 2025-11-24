"""Unit tests for `modules.groups.core.orchestration`.

Tests focus on pure branching and formatting logic with strict isolation.
External provider interactions are simulated with lightweight fake provider
implementations. No network, filesystem, or reconciliation store access.

Scenarios covered:
 - Provider method invocation success/failure/type contract validation
 - Propagation to secondary providers with partial failures and enqueue
 - Read operation handling for list helpers returning normalized groups
 - Response formatting logic including optional field inclusion
 - Early exit when primary write operation fails (no propagation)
"""

# pylint: disable=missing-function-docstring,missing-class-docstring,private-method-access

from typing import Any, Dict, List

import pytest
from modules.groups.core import orchestration
from modules.groups.domain.models import NormalizedGroup
from modules.groups.providers.base import GroupProvider, PrimaryGroupProvider
from modules.groups.providers.contracts import (
    OperationResult,
    OperationStatus,
    ProviderCapabilities,
)


class FakePrimaryProvider(PrimaryGroupProvider):
    """Minimal concrete primary provider for testing orchestration.

    All abstract methods return simple SUCCESS results unless a test
    overrides behavior via instance attributes.
    """

    def __init__(self, fail_add: bool = False, fail_remove: bool = False):
        super().__init__()
        self.fail_add = fail_add
        self.fail_remove = fail_remove

    @property
    def capabilities(self) -> ProviderCapabilities:  # pragma: no cover - trivial
        return ProviderCapabilities(is_primary=True)

    # Required abstract implementations
    def _add_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        if self.fail_add:
            return OperationResult.transient_error("primary add failed")
        return OperationResult.success({"added": member_email})

    def _remove_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        if self.fail_remove:
            return OperationResult.permanent_error("primary remove failed")
        return OperationResult.success({"removed": member_email})

    def _get_group_members_impl(
        self, group_key: str, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"members": []})

    def _list_groups_impl(
        self, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"groups": []})

    def _list_groups_with_members_impl(
        self, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"groups": []})

    def _health_check_impl(self):  # pragma: no cover - unused
        from modules.groups.providers.contracts import HealthCheckResult

        return HealthCheckResult(healthy=True, status="healthy")

    def _validate_permissions_impl(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({})

    def _is_manager_impl(
        self, user_key: str, group_key: str
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({})

    def _list_groups_for_user_impl(
        self, user_key: str, provider_name, **kwargs
    ) -> OperationResult:
        # Return two normalized groups for success path tests
        groups = [
            NormalizedGroup(
                id="g1",
                name="group-one",
                description="Test group one",
                provider="primary",
                members=[],
            ),
            NormalizedGroup(
                id="g2",
                name="group-two",
                description="Test group two",
                provider="primary",
                members=[],
            ),
        ]
        return OperationResult.success({"groups": groups})

    def _list_groups_managed_by_user_impl(
        self, user_key: str, provider_name, **kwargs
    ) -> OperationResult:
        managers = [
            NormalizedGroup(
                id="m1",
                name="managed-one",
                description="Test managed group",
                provider="primary",
                members=[],
            ),
        ]
        return OperationResult.success({"groups": managers})


class FakeSecondaryProvider(GroupProvider):
    """Minimal secondary provider used for propagation tests."""

    def __init__(self, name: str, fail_add: bool = False, fail_remove: bool = False):
        super().__init__()
        self.name = name
        self.fail_add = fail_add
        self.fail_remove = fail_remove

    @property
    def capabilities(self) -> ProviderCapabilities:  # pragma: no cover - trivial
        return ProviderCapabilities(is_primary=False)

    def _add_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        if self.fail_add:
            return OperationResult.permanent_error(f"{self.name} add failed")
        return OperationResult.success({"added": member_email, "provider": self.name})

    def _remove_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        if self.fail_remove:
            return OperationResult.transient_error(f"{self.name} remove failed")
        return OperationResult.success({"removed": member_email, "provider": self.name})

    def _get_group_members_impl(
        self, group_key: str, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"members": []})

    def _list_groups_impl(
        self, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"groups": []})

    def _list_groups_with_members_impl(
        self, **kwargs
    ) -> OperationResult:  # pragma: no cover - unused
        return OperationResult.success({"groups": []})

    def _health_check_impl(self):  # pragma: no cover - unused
        from modules.groups.providers.contracts import HealthCheckResult

        return HealthCheckResult(healthy=True, status="healthy")


@pytest.fixture
def primary_provider():
    return FakePrimaryProvider()


@pytest.fixture
def providers(primary_provider):
    """Return mapping of active providers with primary + two secondaries."""
    return {
        "primary": primary_provider,
        "aws": FakeSecondaryProvider("aws"),
        "okta": FakeSecondaryProvider("okta"),
    }


def _patch_provider_functions(monkeypatch, providers, primary_name="primary"):
    primary = providers[primary_name]
    secondaries = {k: v for k, v in providers.items() if k != primary_name}
    monkeypatch.setattr(orchestration, "get_primary_provider", lambda: primary)
    monkeypatch.setattr(orchestration, "get_secondary_providers", lambda: secondaries)


@pytest.mark.unit
def test_call_provider_method_success(primary_provider):
    result = orchestration._call_provider_method(
        primary_provider, "add_member", "group-1", "user@example.com"
    )
    assert isinstance(result, OperationResult)
    assert result.status == OperationStatus.SUCCESS
    assert result.data["added"] == "user@example.com"


@pytest.mark.unit
def test_call_provider_method_invalid_return_type(monkeypatch, primary_provider):
    class WeirdProvider(FakePrimaryProvider):
        def _add_member_impl(self, group_key: str, member_email: str):  # type: ignore
            return {"unexpected": True}  # Wrong type

    weird = WeirdProvider()
    result = orchestration._call_provider_method(
        weird, "add_member", "g", "m@example.com"
    )
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert "returned dict" in result.message


@pytest.mark.unit
def test_call_provider_method_exception(primary_provider, monkeypatch):
    def boom(*args, **kwargs):  # noqa: D401
        raise RuntimeError("exploded")

    monkeypatch.setattr(primary_provider, "add_member", boom)
    result = orchestration._call_provider_method(
        primary_provider, "add_member", "g", "m@example.com"
    )
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert "exploded" in result.message


@pytest.mark.unit
def test_call_provider_method_missing_method(primary_provider):
    with pytest.raises(AttributeError):
        orchestration._call_provider_method(
            primary_provider, "nonexistent_method", "g", "m@example.com"
        )


@pytest.mark.unit
def test_propagate_to_secondaries_partial_failure(monkeypatch, providers):
    # Fail one secondary
    providers["aws"].fail_add = True
    enqueue_calls: List[Dict[str, Any]] = []

    def fake_enqueue(**kwargs):
        enqueue_calls.append(kwargs)
        return "rec-1"

    _patch_provider_functions(monkeypatch, providers)
    monkeypatch.setattr(orchestration.ri, "enqueue_failed_propagation", fake_enqueue)

    results = orchestration._propagate_to_secondaries(
        primary_group_id="group-primary@example.com",
        member_email="user@example.com",
        op_name="add_member",
        action="add_member",
        correlation_id="cid-123",
    )

    assert set(results.keys()) == {"aws", "okta"}
    assert results["okta"].status == OperationStatus.SUCCESS
    assert results["aws"].status != OperationStatus.SUCCESS
    assert len(enqueue_calls) == 1
    assert enqueue_calls[0]["provider"] == "aws"


@pytest.mark.unit
def test_orchestrate_write_operation_primary_failure(monkeypatch, providers):
    providers["primary"].fail_add = True
    _patch_provider_functions(monkeypatch, providers)
    response = orchestration.add_member_to_group(
        primary_group_id="group-primary@example.com",
        member_email="user@example.com",
        justification="test",
        correlation_id="cid-456",
    )
    assert response["success"] is False
    assert response["primary"]["status"] == OperationStatus.TRANSIENT_ERROR.name
    assert response["propagation"] == {}
    assert response["partial_failures"] is False


@pytest.mark.unit
def test_orchestrate_write_operation_success_with_partial(monkeypatch, providers):
    providers["aws"].fail_add = True
    _patch_provider_functions(monkeypatch, providers)
    response = orchestration.add_member_to_group(
        primary_group_id="group-primary@example.com",
        member_email="user@example.com",
        justification="test",
        correlation_id="cid-789",
    )
    assert response["success"] is True
    assert response["primary"]["status"] == OperationStatus.SUCCESS.name
    assert response["partial_failures"] is True
    assert response["propagation"]["aws"]["status"] != OperationStatus.SUCCESS.name
    assert response["propagation"]["okta"]["status"] == OperationStatus.SUCCESS.name


@pytest.mark.unit
def test_format_orchestration_response_optional_fields(monkeypatch, providers):
    _patch_provider_functions(monkeypatch, providers)
    primary = OperationResult.success({"x": 1})
    primary.error_code = "E123"
    primary.retry_after = 30
    propagation = {
        "aws": OperationResult.transient_error("fail", error_code="P1", retry_after=10),
    }
    response = orchestration._format_orchestration_response(
        primary=primary,
        propagation=propagation,
        partial_failures=True,
        correlation_id="cid-format",
        action="test_action",
        group_id="group-primary@example.com",
        member_email="user@example.com",
    )
    assert response["primary"]["error_code"] == "E123"
    assert response["primary"]["retry_after"] == 30
    assert response["propagation"]["aws"]["error_code"] == "P1"
    assert response["group_id"] == "group-primary@example.com"
    assert response["member_email"] == "user@example.com"
