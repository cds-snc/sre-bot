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
from unittest.mock import MagicMock, patch

from modules.groups import service
from modules.groups import schemas
from modules.groups import validation
from modules.groups.providers.base import OperationResult, OperationStatus


class TestCheckUserIsManager:
    """Tests for _check_user_is_manager helper function."""

    @pytest.fixture
    def mock_primary_provider(self):
        """Mock primary provider with is_manager method."""
        provider = MagicMock()
        provider.is_manager = MagicMock(return_value=True)
        return provider

    @pytest.fixture
    def mock_providers_dict(self, mock_primary_provider):
        """Mock active providers dictionary."""
        return {
            "google": mock_primary_provider,
        }

    def test_check_manager_returns_true_when_manager(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Returns True when user is a manager."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )
        mock_primary_provider.is_manager.return_value = True

        result = service._check_user_is_manager(
            user_email="manager@example.com",
            group_id="test-group",
        )

        assert result is True
        mock_primary_provider.is_manager.assert_called_once_with(
            "manager@example.com", "test-group"
        )

    def test_check_manager_returns_false_when_not_manager(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Returns False when user is not a manager."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )
        mock_primary_provider.is_manager.return_value = False

        result = service._check_user_is_manager(
            user_email="user@example.com",
            group_id="test-group",
        )

        assert result is False

    def test_check_manager_with_operation_result_success(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Handles OperationResult wrapper from provider."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )
        result_obj = OperationResult(
            status=OperationStatus.SUCCESS,
            message="ok",
            data={"is_manager": True},
        )
        mock_primary_provider.is_manager.return_value = result_obj

        result = service._check_user_is_manager(
            user_email="manager@example.com",
            group_id="test-group",
        )

        assert result is True

    def test_check_manager_with_operation_result_failure(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Returns False when OperationResult is not successful."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )
        result_obj = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="error",
            data={},
        )
        mock_primary_provider.is_manager.return_value = result_obj

        result = service._check_user_is_manager(
            user_email="user@example.com",
            group_id="test-group",
        )

        assert result is False

    def test_check_manager_maps_secondary_provider_group_id(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Maps group ID from secondary provider to primary format."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )
        mock_primary_provider.is_manager.return_value = True

        with patch(
            "modules.groups.service.mappings.map_provider_group_id",
            return_value="aws-test-group@cds-snc.ca",
        ) as mock_map:
            result = service._check_user_is_manager(
                user_email="manager@example.com",
                group_id="test-group",
                provider_type="aws",
            )

            assert result is True
            mock_map.assert_called_once()
            # Verify is_manager was called with mapped group ID
            mock_primary_provider.is_manager.assert_called_once_with(
                "manager@example.com", "aws-test-group@cds-snc.ca"
            )

    def test_check_manager_raises_when_primary_provider_missing(
        self, monkeypatch, mock_providers_dict
    ):
        """Raises ValueError when primary provider not available."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: {},  # Empty providers dict
        )

        with pytest.raises(ValueError, match="Primary provider"):
            service._check_user_is_manager(
                user_email="user@example.com",
                group_id="test-group",
            )

    def test_check_manager_raises_on_mapping_failure(
        self, monkeypatch, mock_providers_dict, mock_primary_provider
    ):
        """Raises when group ID mapping fails."""
        monkeypatch.setattr(
            service._providers,
            "get_primary_provider_name",
            lambda: "google",
        )
        monkeypatch.setattr(
            service._providers,
            "get_active_providers",
            lambda: mock_providers_dict,
        )

        with patch(
            "modules.groups.service.mappings.map_provider_group_id",
            side_effect=ValueError("Mapping failed"),
        ):
            with pytest.raises(ValueError, match="Failed to map group ID"):
                service._check_user_is_manager(
                    user_email="user@example.com",
                    group_id="test-group",
                    provider_type="aws",
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
            justification="Adding to team",
            requestor="manager@example.com",
            idempotency_key="key1",
        )

    def test_add_member_succeeds_when_manager(self, monkeypatch, valid_request):
        """add_member succeeds when requestor is manager."""
        with patch(
            "modules.groups.service._check_user_is_manager",
            return_value=True,
        ):
            with patch(
                "modules.groups.service.orchestration.add_member_to_group",
                return_value={
                    "success": True,
                    "group_id": "test-group",
                    "member_email": "newmember@example.com",
                },
            ):
                with patch("modules.groups.service.audit.write_audit_entry"):
                    with patch(
                        "modules.groups.service.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.service.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            result = service.add_member(valid_request)
                            assert result.success is True

    def test_add_member_fails_when_not_manager(self, monkeypatch, valid_request):
        """add_member raises ValidationError when requestor is not manager."""
        with patch(
            "modules.groups.service._check_user_is_manager",
            return_value=False,
        ):
            with patch(
                "modules.groups.service.idempotency.get_cached_response",
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
            "modules.groups.service._check_user_is_manager",
            side_effect=ValueError("Permission check error"),
        ):
            with patch(
                "modules.groups.service.idempotency.get_cached_response",
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
            "modules.groups.service._check_user_is_manager",
            side_effect=mock_check,
        ):
            with patch(
                "modules.groups.service.orchestration.add_member_to_group",
                side_effect=mock_orchestration,
            ):
                with patch("modules.groups.service.audit.write_audit_entry"):
                    with patch(
                        "modules.groups.service.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.service.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            with patch(
                                "modules.groups.service.idempotency.cache_response"
                            ):
                                service.add_member(valid_request)
                                assert call_order == ["check", "orchestration"]


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
            "modules.groups.service._check_user_is_manager",
            return_value=True,
        ):
            with patch(
                "modules.groups.service.orchestration.remove_member_from_group",
                return_value={
                    "success": True,
                    "group_id": "test-group",
                    "member_email": "tomove@example.com",
                },
            ):
                with patch("modules.groups.service.audit.write_audit_entry"):
                    with patch(
                        "modules.groups.service.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.service.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            result = service.remove_member(valid_request)
                            assert result.success is True

    def test_remove_member_fails_when_not_manager(self, monkeypatch, valid_request):
        """remove_member raises ValidationError when requestor is not manager."""
        with patch(
            "modules.groups.service._check_user_is_manager",
            return_value=False,
        ):
            with patch(
                "modules.groups.service.idempotency.get_cached_response",
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
            "modules.groups.service._check_user_is_manager",
            side_effect=ValueError("Permission check error"),
        ):
            with patch(
                "modules.groups.service.idempotency.get_cached_response",
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
            "modules.groups.service._check_user_is_manager",
            side_effect=mock_check,
        ):
            with patch(
                "modules.groups.service.orchestration.remove_member_from_group",
                side_effect=mock_orchestration,
            ):
                with patch("modules.groups.service.audit.write_audit_entry"):
                    with patch(
                        "modules.groups.service.event_system.dispatch_background"
                    ):
                        with patch(
                            "modules.groups.service.idempotency.get_cached_response",
                            return_value=None,
                        ):
                            with patch(
                                "modules.groups.service.idempotency.cache_response"
                            ):
                                service.remove_member(valid_request)
                                assert call_order == ["check", "orchestration"]
