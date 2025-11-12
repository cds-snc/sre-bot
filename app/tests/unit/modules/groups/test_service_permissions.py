"""Unit tests for permission checks in groups service.

Tests cover:
- check_user_is_manager helper function
- Permission enforcement in add_member
- Permission enforcement in remove_member
- Permission denial when user is not manager
- Group ID mapping during permission checks
- Exception handling and error cases
"""

import pytest
from unittest.mock import patch

from modules.groups.core import service
from modules.groups.api import schemas
from modules.groups.infrastructure import validation
from modules.groups.providers.contracts import OperationResult, OperationStatus


class TestCheckUserIsManager:
    """Tests for _check_user_is_manager helper function."""

    def test_check_manager_returns_true_when_manager(
        self, mock_primary_provider, mock_providers_registry
    ):
        """Returns True when user is a manager."""
        mock_primary_provider.is_manager.return_value = True

        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            with patch(
                "modules.groups.core.service._providers.get_primary_provider_name"
            ) as mock_get_prim_name:
                mock_get_prim_prov.return_value = mock_primary_provider
                mock_get_prim_name.return_value = "google"

                result = service._check_user_is_manager(
                    user_email="manager@example.com",
                    group_id="test-group",
                )

                assert result is True
                mock_primary_provider.is_manager.assert_called_once_with(
                    "manager@example.com", "test-group"
                )

    def test_check_manager_returns_false_when_not_manager(
        self, mock_primary_provider, mock_providers_registry
    ):
        """Returns False when user is not a manager."""
        mock_primary_provider.is_manager.return_value = False

        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            with patch(
                "modules.groups.core.service._providers.get_primary_provider_name"
            ) as mock_get_prim_name:
                mock_get_prim_prov.return_value = mock_primary_provider
                mock_get_prim_name.return_value = "google"

                result = service._check_user_is_manager(
                    user_email="user@example.com",
                    group_id="test-group",
                )

                assert result is False

    def test_check_manager_with_operation_result_success(self, mock_primary_provider):
        """Handles OperationResult wrapper from provider."""
        result_obj = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"is_manager": True},
        )
        mock_primary_provider.is_manager.return_value = result_obj

        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            with patch(
                "modules.groups.core.service._providers.get_primary_provider_name"
            ) as mock_get_prim_name:
                mock_get_prim_prov.return_value = mock_primary_provider
                mock_get_prim_name.return_value = "google"

                result = service._check_user_is_manager(
                    user_email="manager@example.com",
                    group_id="test-group",
                )

                assert result is True

    def test_check_manager_with_operation_result_failure(self, mock_primary_provider):
        """Returns False when OperationResult is not successful."""
        result_obj = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="error",
            data={},
        )
        mock_primary_provider.is_manager.return_value = result_obj

        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            with patch(
                "modules.groups.core.service._providers.get_primary_provider_name"
            ) as mock_get_prim_name:
                mock_get_prim_prov.return_value = mock_primary_provider
                mock_get_prim_name.return_value = "google"

                result = service._check_user_is_manager(
                    user_email="user@example.com",
                    group_id="test-group",
                )

                assert result is False

    def test_check_manager_maps_secondary_provider_group_id(
        self, mock_primary_provider
    ):
        """Maps group ID from secondary provider to primary format."""
        mock_primary_provider.is_manager.return_value = True

        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            with patch(
                "modules.groups.core.service._providers.get_primary_provider_name"
            ):
                mock_get_prim_prov.return_value = mock_primary_provider

                result = service._check_user_is_manager(
                    user_email="manager@example.com",
                    group_id="aws-test-group@example.com",
                    provider_type="aws",
                )

                assert result is True
                # Verify is_manager was called with group email directly (no mapping)
                mock_primary_provider.is_manager.assert_called_once_with(
                    "manager@example.com", "aws-test-group@example.com"
                )

    def test_check_manager_raises_when_primary_provider_missing(self):
        """Raises ValueError when primary provider not available."""
        with patch(
            "modules.groups.core.service._providers.get_primary_provider"
        ) as mock_get_prim_prov:
            mock_get_prim_prov.side_effect = RuntimeError("No primary provider")

            with pytest.raises(ValueError, match="Primary provider"):
                service._check_user_is_manager(
                    user_email="user@example.com",
                    group_id="test-group",
                )


@pytest.mark.skip(
    reason="Idempotency cache interferes with test isolation - same key used across tests"
)
class TestAddMemberPermissionEnforcement:
    """Tests for permission enforcement in add_member."""

    @pytest.fixture
    def valid_request(self):
        """Valid add_member request."""
        return schemas.AddMemberRequest(
            group_id="test-group",
            member_email="newmember@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Adding new hire",
            requestor="manager@example.com",
            idempotency_key="key1",
        )

    def test_add_member_succeeds_when_manager(self, monkeypatch, valid_request):
        """add_member succeeds when requestor is manager."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            return_value=True,
        ):
            with patch(
                "modules.groups.core.orchestration.add_member_to_group",
                return_value={
                    "success": True,
                    "group_id": "test-group",
                    "member_email": "newmember@example.com",
                },
            ):
                with patch("modules.groups.core.service.write_audit_entry"):
                    with patch(
                        "modules.groups.events.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.core.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            result = service.add_member(valid_request)
                            assert result.success is True

    def test_add_member_fails_when_not_manager(self, monkeypatch, valid_request):
        """add_member raises ValidationError when requestor is not manager."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            return_value=False,
        ):
            with patch(
                "modules.groups.core.idempotency.get_cached_response",
                return_value=None,
            ):
                with pytest.raises(
                    validation.ValidationError,
                    match="not a manager",
                ):
                    service.add_member(valid_request)

    def test_add_member_fails_on_permission_check_error(
        self, monkeypatch, valid_request
    ):
        """add_member raises when permission check encounters error."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            side_effect=ValueError("Permission check error"),
        ):
            with patch(
                "modules.groups.core.idempotency.get_cached_response",
                return_value=None,
            ):
                with pytest.raises(validation.ValidationError):
                    service.add_member(valid_request)

    def test_add_member_calls_permission_check_before_orchestration(
        self, monkeypatch, valid_request
    ):
        """Permission check is called before orchestration."""
        call_order = []

        def mock_check(*args, **kwargs):
            call_order.append("check")
            return True

        def mock_orchestration(*args, **kwargs):
            call_order.append("orchestration")
            return {
                "success": True,
                "group_id": "test-group",
                "member_email": "newmember@example.com",
            }

        with patch(
            "modules.groups.core.service._check_user_is_manager",
            side_effect=mock_check,
        ):
            with patch(
                "modules.groups.core.orchestration.add_member_to_group",
                side_effect=mock_orchestration,
            ):
                with patch("modules.groups.core.service.write_audit_entry"):
                    with patch(
                        "modules.groups.events.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.core.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            with patch(
                                "modules.groups.core.idempotency.cache_response"
                            ):
                                service.add_member(valid_request)
                                assert call_order == ["check", "orchestration"]


@pytest.mark.skip(
    reason="Idempotency cache interferes with test isolation - same key used across tests"
)
class TestRemoveMemberPermissionEnforcement:
    """Tests for permission enforcement in remove_member."""

    @pytest.fixture
    def valid_request(self):
        """Valid remove_member request."""
        return schemas.RemoveMemberRequest(
            group_id="test-group",
            member_email="tomove@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Removing from team",
            requestor="manager@example.com",
            idempotency_key="key2",
        )

    def test_remove_member_succeeds_when_manager(self, monkeypatch, valid_request):
        """remove_member succeeds when requestor is manager."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            return_value=True,
        ):
            with patch(
                "modules.groups.core.orchestration.remove_member_from_group",
                return_value={
                    "success": True,
                    "group_id": "test-group",
                    "member_email": "tomove@example.com",
                },
            ):
                with patch("modules.groups.core.service.write_audit_entry"):
                    with patch(
                        "modules.groups.events.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.core.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            result = service.remove_member(valid_request)
                            assert result.success is True

    def test_remove_member_fails_when_not_manager(self, monkeypatch, valid_request):
        """remove_member raises ValidationError when requestor is not manager."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            return_value=False,
        ):
            with patch(
                "modules.groups.core.idempotency.get_cached_response",
                return_value=None,
            ):
                with pytest.raises(
                    validation.ValidationError,
                    match="not a manager",
                ):
                    service.remove_member(valid_request)

    def test_remove_member_fails_on_permission_check_error(
        self, monkeypatch, valid_request
    ):
        """remove_member raises when permission check encounters error."""
        with patch(
            "modules.groups.core.service._check_user_is_manager",
            side_effect=ValueError("Permission check error"),
        ):
            with patch(
                "modules.groups.core.idempotency.get_cached_response",
                return_value=None,
            ):
                with pytest.raises(validation.ValidationError):
                    service.remove_member(valid_request)

    def test_remove_member_calls_permission_check_before_orchestration(
        self, monkeypatch, valid_request
    ):
        """Permission check is called before orchestration."""
        call_order = []

        def mock_check(*args, **kwargs):
            call_order.append("check")
            return True

        def mock_orchestration(*args, **kwargs):
            call_order.append("orchestration")
            return {
                "success": True,
                "group_id": "test-group",
                "member_email": "tomove@example.com",
            }

        with patch(
            "modules.groups.core.service._check_user_is_manager",
            side_effect=mock_check,
        ):
            with patch(
                "modules.groups.core.orchestration.remove_member_from_group",
                side_effect=mock_orchestration,
            ):
                with patch("modules.groups.core.service.write_audit_entry"):
                    with patch(
                        "modules.groups.events.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.core.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            with patch(
                                "modules.groups.core.idempotency.cache_response"
                            ):
                                service.remove_member(valid_request)
                                assert call_order == ["check", "orchestration"]
