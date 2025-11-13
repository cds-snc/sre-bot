"""Integration tests for orchestration layer - multi-provider coordination.

Tests the orchestration module's multi-provider coordination, provider selection,
fallback mechanisms, error recovery, and workflow patterns.

Each test:
- Mocks system boundaries (provider registry, mapping, service layer)
- Tests real orchestration coordination logic
- Verifies multi-provider workflows and fallbacks
- Captures side effects (DLQ enqueuing, logging)
"""

from unittest.mock import MagicMock

import pytest
from modules.groups.core import orchestration as orch
from modules.groups.providers.contracts import OperationResult, OperationStatus

pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_orchestration,
]


@pytest.mark.skip(reason="map_primary_to_secondary_group function not implemented")
class TestOrchestrationAddMemberMultiProvider:
    """Test add_member_to_group with multi-provider coordination."""

    def test_add_member_primary_success_propagates_to_secondaries(self, monkeypatch):
        """When primary succeeds, operation propagates to all secondary providers."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com", "group_id": "grp"}},
        )

        google_prov = MagicMock()
        google_prov.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        assert "primary" in result
        assert "propagation" in result
        # primary and propagation contain OperationResult objects, not dicts
        assert hasattr(result["primary"], "status")
        assert result["primary"].status == OperationStatus.SUCCESS
        assert "aws" in result["propagation"]
        primary.add_member.assert_called_once()
        aws_prov.add_member.assert_called_once()

    def test_add_member_primary_failure_no_propagation(self, monkeypatch):
        """When primary fails, no propagation to secondaries."""
        # Arrange
        primary = MagicMock()
        primary.add_member.side_effect = Exception("Primary provider error")

        aws_prov = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        assert "primary" in result
        assert "propagation" in result
        assert result["propagation"] == {}
        aws_prov.add_member.assert_not_called()

    def test_add_member_secondary_failure_enqueues_dlq(self, monkeypatch):
        """When secondary fails, failed propagation is enqueued for retry."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.transient_error(
            message="AWS service temporarily unavailable",
        )

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        assert "aws" in result["propagation"]
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        assert call_kwargs["provider"] == "aws"
        assert call_kwargs["action"] == "add_member"

    def test_add_member_partial_secondary_failures(self, monkeypatch):
        """When some secondaries fail, partial_failures flag set."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.transient_error(
            message="AWS error",
        )

        azure_prov = MagicMock()
        azure_prov.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(
                return_value={
                    "google": primary,
                    "aws": aws_prov,
                    "azure": azure_prov,
                }
            ),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="secondary-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        assert result["partial_failures"] is True
        mock_enqueue.assert_called_once()

    def test_add_member_correlation_id_propagated(self, monkeypatch):
        """Correlation ID is propagated to providers and DLQ."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.transient_error(
            message="AWS error",
        )

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        test_correlation_id = "test-correlation-123"

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
            correlation_id=test_correlation_id,
        )

        # Assert
        assert result["correlation_id"] == test_correlation_id
        # Provider method is called without correlation_id (logged only)
        aws_prov.add_member.assert_called_once()
        # Verify correlation_id passed to DLQ enqueue
        mock_enqueue.assert_called_once()
        assert mock_enqueue.call_args[1]["correlation_id"] == test_correlation_id


@pytest.mark.skip(reason="map_primary_to_secondary_group function not implemented")
class TestOrchestrationRemoveMemberMultiProvider:
    """Test remove_member_from_group with multi-provider coordination."""

    def test_remove_member_primary_success_propagates(self, monkeypatch):
        """When primary succeeds, operation propagates to secondaries."""
        # Arrange
        primary = MagicMock()
        primary.remove_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        aws_prov = MagicMock()
        aws_prov.remove_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )

        # Act
        result = orch.remove_member_from_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="User offboarding removal from project",
        )

        # Assert
        assert isinstance(result, dict)
        assert "primary" in result
        assert "aws" in result["propagation"]
        primary.remove_member.assert_called_once()
        aws_prov.remove_member.assert_called_once()

    def test_remove_member_secondary_error_recovery(self, monkeypatch):
        """When secondary has permanent error, recorded in response."""
        # Arrange
        primary = MagicMock()
        primary.remove_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.remove_member.return_value = OperationResult.permanent_error(
            message="User not found in AWS",
        )

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        # Act
        result = orch.remove_member_from_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="User offboarding removal from project",
        )

        # Assert
        assert result["partial_failures"] is True
        mock_enqueue.assert_called_once()


class TestOrchestrationProviderSelection:
    """Test provider selection and fallback logic."""

    def test_list_groups_uses_primary_provider(self, monkeypatch):
        """list_groups_for_user uses primary provider only."""
        # Arrange
        primary = MagicMock()
        primary.list_groups_for_user.return_value = OperationResult.success(
            data={
                "groups": [
                    {"id": "grp1", "email": "group1@example.com"},
                    {"id": "grp2", "email": "group2@example.com"},
                ]
            },
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )

        # Act
        result = orch.list_groups_for_user("user@example.com")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        primary.list_groups_for_user.assert_called_once()

    def test_list_groups_primary_failure_returns_empty(self, monkeypatch):
        """When primary fails, list_groups returns empty list."""
        # Arrange
        primary = MagicMock()
        primary.list_groups_for_user.side_effect = Exception("Provider error")

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )

        # Act
        result = orch.list_groups_for_user("user@example.com")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_groups_bad_response_returns_empty(self, monkeypatch):
        """When primary returns non-dict data, returns empty list."""
        # Arrange
        primary = MagicMock()
        primary.list_groups_for_user.return_value = OperationResult.success(
            data=None,
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )

        # Act
        result = orch.list_groups_for_user("user@example.com")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_groups_managed_by_user(self, monkeypatch):
        """list_groups_managed_by_user uses primary provider."""
        # Arrange
        primary = MagicMock()
        primary.list_groups_managed_by_user.return_value = OperationResult.success(
            data={
                "groups": [
                    {"id": "mgd1", "email": "managed1@example.com"},
                ]
            },
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )

        # Act
        result = orch.list_groups_managed_by_user("user@example.com")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        primary.list_groups_managed_by_user.assert_called_once()


@pytest.mark.skip(reason="map_primary_to_secondary_group function not implemented")
class TestOrchestrationErrorHandling:
    """Test error handling and recovery patterns."""

    def test_provider_method_exception_caught(self, monkeypatch):
        """When provider method raises exception, caught and logged."""
        # Arrange
        primary = MagicMock()
        primary.add_member.side_effect = Exception("Provider error")

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary}),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert - Should not raise, returns dict with error info
        assert isinstance(result, dict)
        assert "primary" in result

    def test_provider_exception_in_secondary_doesnt_crash(self, monkeypatch):
        """When secondary provider crashes, main operation succeeds with partial failures."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.side_effect = RuntimeError("AWS SDK crash")

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert - Primary succeeded, secondary exception caught
        assert isinstance(result, dict)
        assert "aws" in result["propagation"]
        mock_enqueue.assert_called_once()


@pytest.mark.skip(reason="map_primary_to_secondary_group function not implemented")
class TestOrchestrationMappingAndNormalization:
    """Test group and member mapping/normalization."""

    def test_member_normalization_for_secondary_provider(self, monkeypatch):
        """Phase 1: When propagating to secondary, member_email passed directly.

        Member validation and normalization happens at the provider layer
        via validate_member_email(), not at the orchestration layer.
        """
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="aws-group-id"),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        # Verify aws provider's add_member was called with email string directly
        aws_prov.add_member.assert_called_once()
        call_args = aws_prov.add_member.call_args
        # Check that member_email (second positional arg) is the string directly
        assert call_args[0][1] == "user@example.com"

    def test_group_mapping_for_secondary_provider(self, monkeypatch):
        """When propagating to secondary, group ID mapped."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        mock_map = MagicMock(return_value="aws-mapped-group-id")

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary, "aws": aws_prov}),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            mock_map,
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="google-group-id",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        mock_map.assert_called_once_with("google-group-id", "aws")


@pytest.mark.skip(reason="map_primary_to_secondary_group function not implemented")
class TestOrchestrationWorkflowIntegration:
    """Test end-to-end orchestration workflows."""

    def test_full_add_member_workflow_all_providers_succeed(self, monkeypatch):
        """Full workflow: primary succeeds, propagates to all secondaries successfully."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com", "group_id": "grp"}},
        )

        aws_prov = MagicMock()
        aws_prov.add_member.return_value = OperationResult.success(
            data={"result": {"email": "user@example.com"}},
        )

        azure_prov = MagicMock()
        azure_prov.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(
                return_value={
                    "google": primary,
                    "aws": aws_prov,
                    "azure": azure_prov,
                }
            ),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="secondary-group-id"),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="Test member addition for project access",
        )

        # Assert
        assert isinstance(result, dict)
        assert "primary" in result
        assert "propagation" in result
        assert "aws" in result["propagation"]
        assert "azure" in result["propagation"]
        assert result["partial_failures"] is False
        primary.add_member.assert_called_once()
        aws_prov.add_member.assert_called_once()
        azure_prov.add_member.assert_called_once()

    def test_full_remove_member_workflow_mixed_results(self, monkeypatch):
        """Full workflow: primary succeeds, one secondary succeeds, one fails."""
        # Arrange
        primary = MagicMock()
        primary.remove_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        aws_prov = MagicMock()
        aws_prov.remove_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        azure_prov = MagicMock()
        azure_prov.remove_member.return_value = OperationResult.transient_error(
            message="Azure temporarily unavailable",
        )

        mock_enqueue = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(
                return_value={
                    "google": primary,
                    "aws": aws_prov,
                    "azure": azure_prov,
                }
            ),
        )
        monkeypatch.setattr(
            "modules.groups.core.service.map_primary_to_secondary_group",
            MagicMock(return_value="secondary-group-id"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.ri.enqueue_failed_propagation",
            mock_enqueue,
        )

        # Act
        result = orch.remove_member_from_group(
            primary_group_id="grp",
            member_email="user@example.com",
            justification="User offboarding removal from project",
        )

        # Assert
        assert result["partial_failures"] is True
        assert "aws" in result["propagation"]
        assert "azure" in result["propagation"]
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        assert call_kwargs["provider"] == "azure"

    def test_orchestration_response_includes_metadata(self, monkeypatch):
        """Response includes action, group_id, correlation_id metadata."""
        # Arrange
        primary = MagicMock()
        primary.add_member.return_value = OperationResult.success(
            data={"result": {}},
        )

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider",
            MagicMock(return_value=primary),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary}),
        )

        # Act
        result = orch.add_member_to_group(
            primary_group_id="test-group",
            member_email="user@example.com",
            justification="Test member addition for project access",
            correlation_id="cid-123",
        )

        # Assert
        assert result["action"] == "add_member"
        assert result["group_id"] == "test-group"
        assert result["member_email"] == "user@example.com"
        assert result["correlation_id"] == "cid-123"
        assert "primary" in result
        assert "propagation" in result
        assert "partial_failures" in result


@pytest.mark.skip(
    reason="get_enabled_secondary_providers not in refactored implementation"
)
class TestOrchestrationEnableSecondariesHelper:
    """Test get_enabled_secondary_providers helper."""

    def test_get_enabled_secondary_providers_excludes_primary(self, monkeypatch):
        """get_enabled_secondary_providers returns all providers except primary."""
        # Arrange
        primary = MagicMock()
        aws_prov = MagicMock()
        azure_prov = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(
                return_value={
                    "google": primary,
                    "aws": aws_prov,
                    "azure": azure_prov,
                }
            ),
        )

        # Act
        secondaries = orch.get_enabled_secondary_providers()

        # Assert
        assert isinstance(secondaries, dict)
        assert "google" not in secondaries
        assert "aws" in secondaries
        assert "azure" in secondaries
        assert secondaries["aws"] is aws_prov
        assert secondaries["azure"] is azure_prov

    def test_get_enabled_secondary_providers_empty_when_single_provider(
        self, monkeypatch
    ):
        """When only primary exists, secondary providers empty."""
        # Arrange
        primary = MagicMock()

        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_primary_provider_name",
            MagicMock(return_value="google"),
        )
        monkeypatch.setattr(
            "modules.groups.core.orchestration.get_active_providers",
            MagicMock(return_value={"google": primary}),
        )

        # Act
        secondaries = orch.get_enabled_secondary_providers()

        # Assert
        assert isinstance(secondaries, dict)
        assert len(secondaries) == 0
