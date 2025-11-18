"""Unit tests for Phase 1 changes to Google Workspace provider.

Tests cover:
- Email-based add_member and remove_member operations
- Email validation using shared validate_member_email function
- Domain configuration loading from settings
- Permission validation delegation to is_manager_impl
- Health check returning HealthCheckResult
"""

import pytest
from unittest.mock import patch, Mock
from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
from modules.groups.providers.base import (
    validate_member_email,
)
from modules.groups.providers.contracts import OperationStatus, HealthCheckResult


@pytest.mark.unit
class TestGoogleWorkspaceEmailBasedOperations:
    """Test email-based add_member and remove_member operations."""

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_add_member_with_valid_email(self, mock_settings, mock_google_directory):
        """Test adding a member with valid email address."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock Google Directory API response
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        mock_google_directory.insert_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.add_member("group@company.com", "user@company.com")

        assert result.status == OperationStatus.SUCCESS
        mock_google_directory.insert_member.assert_called_once()

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_add_member_validates_email_format(
        self, mock_settings, mock_google_directory
    ):
        """Test that add_member validates email format internally."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()

        # Invalid email (no @) should fail gracefully through provider_operation decorator
        result = provider.add_member("group@company.com", "invalid-email")
        # The decorator catches validation errors and returns transient error
        assert result.status == OperationStatus.TRANSIENT_ERROR

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_remove_member_with_valid_email(self, mock_settings, mock_google_directory):
        """Test removing a member with valid email address."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock Google Directory API response
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {}
        mock_google_directory.delete_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.remove_member("group@company.com", "user@company.com")

        assert result.status == OperationStatus.SUCCESS
        mock_google_directory.delete_member.assert_called_once()

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_remove_member_validates_email_format(
        self, mock_settings, mock_google_directory
    ):
        """Test that remove_member validates email format internally."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()

        # Invalid email (empty) should fail through provider_operation decorator
        result = provider.remove_member("group@company.com", "")
        # The decorator catches validation errors and returns transient error
        assert result.status == OperationStatus.TRANSIENT_ERROR


@pytest.mark.unit
class TestGoogleWorkspaceDomainConfiguration:
    """Test domain configuration loading from settings."""

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_from_configured_setting(self, mock_settings):
        """Test loading domain from groups.group_domain setting."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "company.com"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_from_sre_email_fallback(self, mock_settings):
        """Test loading domain from sre_email setting as fallback."""
        mock_settings.groups.group_domain = None
        mock_settings.sre_email = "sre@fallback.domain.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "fallback.domain.com"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_none_when_not_configured(self, mock_settings):
        """Test that domain is None when neither setting is available."""
        mock_settings.groups.group_domain = None
        mock_settings.sre_email = None
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain is None

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_prefers_configured_over_fallback(self, mock_settings):
        """Test that configured setting is preferred over fallback."""
        mock_settings.groups.group_domain = "primary.com"
        mock_settings.sre_email = "sre@fallback.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "primary.com"


@pytest.mark.unit
class TestGoogleWorkspacePermissionValidation:
    """Test permission validation delegation."""

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_validate_permissions_checks_manager_role(
        self, mock_settings, mock_google_directory
    ):
        """Test that validate_permissions checks manager role."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock is_manager response for MANAGER role
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {"role": "MANAGER"}
        mock_google_directory.get_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        # Call the wrapper method (which returns OperationResult)
        result = provider.validate_permissions(
            "user@company.com", "group@company.com", "add_member"
        )

        # Verify the method was called (indicating delegation happened)
        assert result.status == OperationStatus.SUCCESS
        mock_google_directory.get_member.assert_called()

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_is_manager_returns_true_for_managers(
        self, mock_settings, mock_google_directory
    ):
        """Test that is_manager returns True for MANAGER or OWNER role."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock manager response
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {"role": "MANAGER"}
        mock_google_directory.get_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.is_manager("user@company.com", "group@company.com")

        assert result.status == OperationStatus.SUCCESS
        # The data contains the boolean wrapped by decorator
        assert "is_manager" in result.data
        assert result.data["is_manager"] is True

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_is_manager_returns_false_for_members(
        self, mock_settings, mock_google_directory
    ):
        """Test that is_manager returns False for MEMBER role."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock member response (not manager)
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {"role": "MEMBER"}
        mock_google_directory.get_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.is_manager("user@company.com", "group@company.com")

        assert result.status == OperationStatus.SUCCESS
        assert result.data["is_manager"] is False


@pytest.mark.unit
class TestGoogleWorkspaceHealthCheck:
    """Test health check returning HealthCheckResult internally."""

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_health_check_success_internally_returns_healthcheckresult(
        self, mock_settings, mock_google_directory
    ):
        """Test successful health check returns HealthCheckResult internally."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock successful list_groups response
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = [{"id": "group-123", "email": "test@company.com"}]
        mock_google_directory.list_groups.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.health_check()

        # health_check is wrapped by provider_operation, returns OperationResult
        # but internally _health_check_impl returns HealthCheckResult
        assert result.status == OperationStatus.SUCCESS
        # The wrapper puts the HealthCheckResult in data with key "health"
        assert "health" in result.data
        health_result = result.data["health"]
        assert isinstance(health_result, HealthCheckResult)
        assert health_result.healthy is True
        assert health_result.status == "healthy"
        assert health_result.details is not None
        assert health_result.details.get("domain") == "company.com"

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_health_check_failure_internally_returns_healthcheckresult(
        self, mock_settings, mock_google_directory
    ):
        """Test failed health check returns HealthCheckResult internally."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock failed API response
        mock_response = Mock()
        mock_response.success = False
        mock_response.status = 401
        mock_google_directory.list_groups.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.health_check()

        # health_check is wrapped by provider_operation, returns OperationResult
        assert result.status == OperationStatus.SUCCESS
        # The wrapper puts the HealthCheckResult in data with key "health"
        assert "health" in result.data
        health_result = result.data["health"]
        assert isinstance(health_result, HealthCheckResult)
        assert health_result.healthy is False
        assert health_result.status == "unhealthy"


@pytest.mark.unit
class TestGoogleWorkspaceEmailValidation:
    """Test email validation using shared function."""

    def test_validate_member_email_used(self):
        """Test that validate_member_email function is available."""
        # This tests that the shared function exists and works
        email = validate_member_email("user@example.com")
        assert email == "user@example.com"

    def test_validate_member_email_normalizes(self):
        """Test that email validation normalizes addresses."""
        email = validate_member_email("User@EXAMPLE.COM")
        assert email == "User@example.com"  # Domain lowercase

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_add_member_normalizes_email(self, mock_settings, mock_google_directory):
        """Test that add_member normalizes email before sending to API."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        # Mock successful response
        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        mock_google_directory.insert_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.add_member("group@company.com", "User@COMPANY.COM")

        assert result.status == OperationStatus.SUCCESS
        # Verify normalized email was passed to API
        call_args = mock_google_directory.insert_member.call_args
        assert call_args[0][1] == "User@company.com"  # Normalized


@pytest.mark.unit
class TestGoogleWorkspaceLocalPartExtraction:
    """Test local part extraction for group IDs."""

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_email(self, mock_settings):
        """Test extracting local part from email."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part("developers@company.com")
        assert result == "developers"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_non_email(self, mock_settings):
        """Test extracting local part from non-email string."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part("developers")
        assert result == "developers"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_none(self, mock_settings):
        """Test extracting local part from None."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part(None)
        assert result is None

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_handles_multiple_at(self, mock_settings):
        """Test local part extraction with display names."""
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        # email-validator handles display names, but extract_local_part just splits on @
        result = provider._extract_local_part("user+tag@company.com")
        assert result == "user+tag"
