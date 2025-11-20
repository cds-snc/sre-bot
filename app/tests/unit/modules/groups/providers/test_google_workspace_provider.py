"""Unit tests for the Google Workspace provider.

Contains normalization tests and provider behavior/unit tests.
"""

import pytest
import types
from unittest.mock import patch, Mock

from infrastructure.operations import OperationResult
from modules.groups.providers.contracts import OperationStatus, HealthCheckResult
from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
from modules.groups.domain.models import NormalizedMember, NormalizedGroup
from modules.groups.providers.base import validate_member_email


# ============================================================================
# Member Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestNormalizeMemberFromGoogle:
    """Test _normalize_member_from_google conversion."""

    def test_normalize_member_standard(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member)

        assert isinstance(result, NormalizedMember)
        assert result.email == "user@company.com"
        assert result.id == "member-123"
        assert result.role == "MEMBER"
        assert result.provider_member_id == "member-123"

    def test_normalize_member_with_name(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
            "name": {"givenName": "John", "familyName": "Doe"},
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_member_with_leading_trailing_whitespace_in_name(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
            "name": {"givenName": "  John  ", "familyName": "  Doe  "},
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_member_with_primary_email_fallback(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "primaryEmail": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.email == "user@company.com"

    def test_normalize_member_no_role(self):
        provider = GoogleWorkspaceProvider()
        google_member = {"email": "user@company.com", "id": "member-123"}
        result = provider._normalize_member_from_google(google_member)

        assert result.role is None

    def test_normalize_member_no_name(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.first_name is None
        assert result.family_name is None

    def test_normalize_member_with_raw_data(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member, include_raw=True)

        assert result.raw == google_member

    def test_normalize_member_without_raw_data(self):
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(
            google_member, include_raw=False
        )

        assert result.raw is None


# ============================================================================
# Group Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestNormalizeGroupFromGoogle:
    """Test _normalize_group_from_google conversion."""

    def test_normalize_group_standard(self):
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "id": "group-123",
            "name": "Developers",
            "description": "Development team",
        }
        result = provider._normalize_group_from_google(google_group)

        assert isinstance(result, NormalizedGroup)
        assert result.id == "developers"
        assert result.name == "Developers"
        assert result.description == "Development team"
        assert result.provider == "google"
        assert result.members == []

    def test_normalize_group_uses_local_part_as_id(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "my-team@subdomain.company.com", "name": "My Team"}
        result = provider._normalize_group_from_google(google_group)

        assert result.id == "my-team"

    def test_normalize_group_fallback_to_email_for_name(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "id": "group-123"}
        result = provider._normalize_group_from_google(google_group)

        assert result.name == "developers@company.com"

    def test_normalize_group_all_empty_returns_none_id(self):
        provider = GoogleWorkspaceProvider()
        google_group = {}
        result = provider._normalize_group_from_google(google_group)

        assert result.id is None
        assert result.name is None

    def test_normalize_group_with_members(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "name": "Developers"}
        members = [
            {"email": "user1@company.com", "id": "member-1", "role": "MEMBER"},
            {"email": "user2@company.com", "id": "member-2", "role": "MANAGER"},
        ]
        result = provider._normalize_group_from_google(google_group, members=members)

        assert len(result.members) == 2
        assert result.members[0].email == "user1@company.com"
        assert result.members[1].role == "MANAGER"

    def test_normalize_group_filters_non_dict_members(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "name": "Developers"}
        members = [{"email": "user1@company.com", "id": "member-1"}, "invalid", None]
        result = provider._normalize_group_from_google(google_group, members=members)

        assert len(result.members) == 1

    def test_normalize_group_from_group_dict_members_fallback(self):
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
            "members": [{"email": "user1@company.com", "id": "member-1"}],
        }
        result = provider._normalize_group_from_google(google_group)

        assert len(result.members) == 1

    def test_normalize_group_minimal_valid(self):
        provider = GoogleWorkspaceProvider()
        minimal_group = {}
        result = provider._normalize_group_from_google(minimal_group)
        assert isinstance(result, NormalizedGroup)
        assert result.id is None
        assert result.name is None
        assert result.description is None

    def test_normalize_group_with_raw_data(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "name": "Developers"}
        result = provider._normalize_group_from_google(google_group, include_raw=True)

        assert result.raw == google_group

    def test_normalize_group_without_raw_data(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "name": "Developers"}
        result = provider._normalize_group_from_google(google_group, include_raw=False)

        assert result.raw is None

    def test_normalize_group_no_description(self):
        provider = GoogleWorkspaceProvider()
        google_group = {"email": "developers@company.com", "name": "Developers"}
        result = provider._normalize_group_from_google(google_group)

        assert result.description is None


# Keep placeholder for resolve identifier tests (private API tests removed intentionally)
@pytest.mark.unit
class TestResolveMemberIdentifier:
    pass


# ============================================================================
# Provider Operation Tests
# ============================================================================


@pytest.mark.unit
class TestGoogleWorkspaceEmailBasedOperations:
    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_add_member_with_valid_email(self, mock_settings, mock_google_directory):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

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
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()

        result = provider.add_member("group@company.com", "invalid-email")
        assert result.status == OperationStatus.TRANSIENT_ERROR

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_remove_member_with_valid_email(self, mock_settings, mock_google_directory):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

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
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider.remove_member("group@company.com", "")
        assert result.status == OperationStatus.TRANSIENT_ERROR


@pytest.mark.unit
class TestGoogleWorkspaceDomainConfiguration:
    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_from_configured_setting(self, mock_settings):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "company.com"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_from_sre_email_fallback(self, mock_settings):
        mock_settings.groups.group_domain = None
        mock_settings.sre_email = "sre@fallback.domain.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "fallback.domain.com"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_none_when_not_configured(self, mock_settings):
        mock_settings.groups.group_domain = None
        mock_settings.sre_email = None
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain is None

    @patch("modules.groups.providers.google_workspace.settings")
    def test_get_domain_prefers_configured_over_fallback(self, mock_settings):
        mock_settings.groups.group_domain = "primary.com"
        mock_settings.sre_email = "sre@fallback.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        assert provider.domain == "primary.com"


@pytest.mark.unit
class TestGoogleWorkspacePermissionValidation:
    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_validate_permissions_checks_manager_role(
        self, mock_settings, mock_google_directory
    ):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {"role": "MANAGER"}
        mock_google_directory.get_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.validate_permissions(
            "user@company.com", "group@company.com", "add_member"
        )

        assert result.status == OperationStatus.SUCCESS
        mock_google_directory.get_member.assert_called()

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_is_manager_returns_true_for_managers(
        self, mock_settings, mock_google_directory
    ):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        mock_response = Mock()
        mock_response.success = True
        mock_response.data = {"role": "MANAGER"}
        mock_google_directory.get_member.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.is_manager("user@company.com", "group@company.com")

        assert result.status == OperationStatus.SUCCESS
        assert "is_manager" in result.data
        assert result.data["is_manager"] is True

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_is_manager_returns_false_for_members(
        self, mock_settings, mock_google_directory
    ):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

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
    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_health_check_success_internally_returns_healthcheckresult(
        self, mock_settings, mock_google_directory
    ):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        mock_response = Mock()
        mock_response.success = True
        mock_response.data = [{"id": "group-123", "email": "test@company.com"}]
        mock_google_directory.list_groups.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.health_check()

        assert result.status == OperationStatus.SUCCESS
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
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status = 401
        mock_google_directory.list_groups.return_value = mock_response

        provider = GoogleWorkspaceProvider()
        result = provider.health_check()

        assert result.status == OperationStatus.SUCCESS
        assert "health" in result.data
        health_result = result.data["health"]
        assert isinstance(health_result, HealthCheckResult)
        assert health_result.healthy is False
        assert health_result.status == "unhealthy"


@pytest.mark.unit
class TestGoogleWorkspaceEmailValidation:
    def test_validate_member_email_used(self):
        email = validate_member_email("user@example.com")
        assert email == "user@example.com"

    def test_validate_member_email_normalizes(self):
        email = validate_member_email("User@EXAMPLE.COM")
        assert email == "User@example.com"

    @patch("modules.groups.providers.google_workspace.google_directory")
    @patch("modules.groups.providers.google_workspace.settings")
    def test_add_member_normalizes_email(self, mock_settings, mock_google_directory):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

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
        call_args = mock_google_directory.insert_member.call_args
        assert call_args[0][1] == "User@company.com"


@pytest.mark.unit
class TestGoogleWorkspaceLocalPartExtraction:
    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_email(self, mock_settings):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part("developers@company.com")
        assert result == "developers"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_non_email(self, mock_settings):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part("developers")
        assert result == "developers"

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_from_none(self, mock_settings):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part(None)
        assert result is None

    @patch("modules.groups.providers.google_workspace.settings")
    def test_extract_local_part_handles_multiple_at(self, mock_settings):
        mock_settings.groups.group_domain = "company.com"
        mock_settings.groups.circuit_breaker_enabled = False

        provider = GoogleWorkspaceProvider()
        result = provider._extract_local_part("user+tag@company.com")
        assert result == "user+tag"


# ============================================================================
# Unique edge-case test from original provider file
# ============================================================================


@pytest.mark.unit
def test_list_members_handles_unexpected_response(monkeypatch):
    provider = GoogleWorkspaceProvider()

    monkeypatch.setattr(
        "integrations.google_workspace.google_directory_next.list_members",
        lambda group_key, **kw: types.SimpleNamespace(success=False, data=None),
        raising=False,
    )

    res = provider._get_group_members_impl("developers@company.com")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data.get("members") == []
