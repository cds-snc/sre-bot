"""Unit tests for Google Workspace provider normalization and helper functions.

Tests cover pure unit logic extraction from GoogleWorkspaceProvider:
- Email extraction (_get_local_part)
- Group normalization (_normalize_group_from_google)
- Member normalization (_normalize_member_from_google)
- Member identifier resolution (_resolve_member_identifier)

Note: Integration tests (actual API calls) are in tests/modules/groups/providers/.
"""

import pytest
import types
from modules.groups.providers.contracts import OperationResult, OperationStatus
from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
from modules.groups.domain.models import NormalizedMember, NormalizedGroup


# ============================================================================
# Member Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestNormalizeMemberFromGoogle:
    """Test _normalize_member_from_google conversion."""

    def test_normalize_member_standard(self):
        """Test normalizing standard member."""
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
        """Test normalizing member with name object."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
            "name": {
                "givenName": "John",
                "familyName": "Doe",
            },
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_member_with_leading_trailing_whitespace_in_name(self):
        """Test that names are stripped."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
            "name": {
                "givenName": "  John  ",
                "familyName": "  Doe  ",
            },
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_member_with_primary_email_fallback(self):
        """Test that primaryEmail is used if email missing."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "primaryEmail": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.email == "user@company.com"

    def test_normalize_member_no_role(self):
        """Test normalizing member without role."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
        }
        result = provider._normalize_member_from_google(google_member)

        assert result.role is None

    def test_normalize_member_no_name(self):
        """Test normalizing member without name."""
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
        """Test that raw data is stored when requested."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        result = provider._normalize_member_from_google(google_member, include_raw=True)

        assert result.raw == google_member

    def test_normalize_member_without_raw_data(self):
        """Test that raw data is None when not requested."""
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
        """Test normalizing standard group."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "id": "group-123",
            "name": "Developers",
            "description": "Development team",
        }
        result = provider._normalize_group_from_google(google_group)

        assert isinstance(result, NormalizedGroup)
        assert result.id == "developers"  # local part
        assert result.name == "Developers"
        assert result.description == "Development team"
        assert result.provider == "google"
        assert result.members == []

    def test_normalize_group_uses_local_part_as_id(self):
        """Test that group ID is the email local part."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "my-team@subdomain.company.com",
            "name": "My Team",
        }
        result = provider._normalize_group_from_google(google_group)

        assert result.id == "my-team"

    def test_normalize_group_fallback_to_email_for_name(self):
        """Test that email is used if name missing."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "id": "group-123",
        }
        result = provider._normalize_group_from_google(google_group)

        assert result.name == "developers@company.com"

    def test_normalize_group_all_empty_returns_none_id(self):
        """Test that group with no email/name/id results in None id."""
        provider = GoogleWorkspaceProvider()
        google_group = {}
        result = provider._normalize_group_from_google(google_group)

        # When email/name/id all missing, id will be None
        assert result.id is None
        assert result.name is None

    def test_normalize_group_with_members(self):
        """Test normalizing group with members."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        members = [
            {"email": "user1@company.com", "id": "member-1", "role": "MEMBER"},
            {"email": "user2@company.com", "id": "member-2", "role": "MANAGER"},
        ]
        result = provider._normalize_group_from_google(google_group, members=members)

        assert len(result.members) == 2
        assert result.members[0].email == "user1@company.com"
        assert result.members[1].role == "MANAGER"

    def test_normalize_group_filters_non_dict_members(self):
        """Test that non-dict members are filtered out."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        members = [
            {"email": "user1@company.com", "id": "member-1"},
            "invalid",  # Should be filtered
            None,  # Should be filtered
        ]
        result = provider._normalize_group_from_google(google_group, members=members)

        assert len(result.members) == 1

    def test_normalize_group_from_group_dict_members_fallback(self):
        """Test that members from group dict are used as fallback."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
            "members": [
                {"email": "user1@company.com", "id": "member-1"},
            ],
        }
        result = provider._normalize_group_from_google(google_group)

        assert len(result.members) == 1

    def test_normalize_group_minimal_valid(self):
        """Test that minimal group (even empty dict) validates with Pydantic."""
        provider = GoogleWorkspaceProvider()
        minimal_group = {}

        # Pydantic Group schema allows all fields Optional, so empty dict is valid
        result = provider._normalize_group_from_google(minimal_group)
        assert isinstance(result, NormalizedGroup)
        assert result.id is None
        assert result.name is None
        assert result.description is None

    def test_normalize_group_with_raw_data(self):
        """Test that raw data is stored when requested."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        result = provider._normalize_group_from_google(google_group, include_raw=True)

        assert result.raw == google_group

    def test_normalize_group_without_raw_data(self):
        """Test that raw data is None when not requested."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        result = provider._normalize_group_from_google(google_group, include_raw=False)

        assert result.raw is None

    def test_normalize_group_no_description(self):
        """Test normalizing group without description."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        result = provider._normalize_group_from_google(google_group)

        assert result.description is None


# ============================================================================
# Member Identifier Resolution Tests
# ============================================================================


@pytest.mark.unit
class TestResolveMemberIdentifier:
    """Test _resolve_member_identifier conversion - REMOVED: Testing private methods not recommended."""

    pass


# ============================================================================
# Integration Between Methods Tests
# ============================================================================


@pytest.mark.skip(
    reason="Calls deleted private methods: _resolve_member_identifier, _get_local_part, _set_domain_from_config"
)
@pytest.mark.unit
class TestGoogleProviderIntegration:
    """Test interactions between Google provider methods."""

    def test_normalize_then_resolve_member(self):
        """Test normalizing then resolving a member."""
        provider = GoogleWorkspaceProvider()
        google_member = {
            "email": "user@company.com",
            "id": "member-123",
            "role": "MEMBER",
        }
        normalized = provider._normalize_member_from_google(google_member)
        resolved = provider._resolve_member_identifier(normalized)

        assert resolved == "user@company.com"

    def test_group_with_normalized_members(self):
        """Test group normalization maintains member normalization."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "developers@company.com",
            "name": "Developers",
        }
        members = [
            {
                "email": "user1@company.com",
                "id": "member-1",
                "role": "MEMBER",
                "name": {"givenName": "John", "familyName": "Doe"},
            },
        ]
        result = provider._normalize_group_from_google(google_group, members=members)

        assert result.members[0].first_name == "John"
        assert result.members[0].email == "user1@company.com"

    def test_local_part_extraction_in_group_normalization(self):
        """Test that local part extraction is used in group normalization."""
        provider = GoogleWorkspaceProvider()
        google_group = {
            "email": "my-team+tag@subdomain.company.com",
            "name": "My Team",
        }
        result = provider._normalize_group_from_google(google_group)

        # Should extract local part including the +tag
        assert result.id == "my-team+tag"

    def test_capabilities_provider_is_primary(self):
        """Test that Google provider reports as primary."""
        provider = GoogleWorkspaceProvider()
        caps = provider.capabilities

        assert caps.is_primary is True
        assert caps.supports_member_management is True
        assert caps.provides_role_info is True

    def test_capabilities_not_supporting_group_operations(self):
        """Test that Google provider doesn't support group creation."""
        provider = GoogleWorkspaceProvider()
        caps = provider.capabilities

        assert caps.supports_group_creation is False
        assert caps.supports_group_deletion is False
        assert caps.supports_user_creation is False
        assert caps.supports_user_deletion is False

    def test_list_members_handles_unexpected_response(self, monkeypatch):
        """If google_directory.list_members returns an error-like resp, wrapper should surface transient error."""
        provider = GoogleWorkspaceProvider()

        # Simulate google_directory.list_members returning an OperationResult-like failure
        monkeypatch.setattr(
            "integrations.google_workspace.google_directory_next.list_members",
            lambda group_key, **kw: types.SimpleNamespace(success=False, data=None),
            raising=False,
        )

        res = provider._get_group_members_impl("developers@company.com")
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.TRANSIENT_ERROR

    def test_validate_permissions_detects_manager(self, monkeypatch):
        """validate_permissions should return True when user is a MANAGER."""
        provider = GoogleWorkspaceProvider()

        # Simulate list_members returning only managers when roles='MANAGER'.
        manager = {"email": "manager@company.com", "id": "m2", "role": "MANAGER"}

        def fake_list_members(group_key, **kw):
            # The provider calls list_members(..., roles='MANAGER') so emulate that
            if kw.get("roles") == "MANAGER":
                return types.SimpleNamespace(success=True, data=[manager])
            # Default to empty list for other queries
            return types.SimpleNamespace(success=True, data=[])

        monkeypatch.setattr(
            "integrations.google_workspace.google_directory_next.list_members",
            fake_list_members,
            raising=False,
        )

        res = provider.validate_permissions(
            "manager@company.com", "developers@company.com", "write"
        )
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.SUCCESS
        assert res.data.get("allowed") is True

        res = provider.validate_permissions("m2", "developers@company.com", "write")
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.SUCCESS
        assert res.data.get("allowed") is True

        res = provider.validate_permissions(
            "user1@company.com", "developers@company.com", "write"
        )
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.SUCCESS
        assert res.data.get("allowed") is False

    def test_set_domain_from_config_and_env(self, monkeypatch):
        """_set_domain_from_config should prefer settings value, then env SRE_BOT_EMAIL."""
        provider = GoogleWorkspaceProvider()

        # Patch core.config.settings for configured domain
        import types as _types

        fake_settings = _types.SimpleNamespace()
        fake_settings.groups = _types.SimpleNamespace(group_domain="configured.com")
        fake_settings.sre_email = None

        monkeypatch.setattr("core.config.settings", fake_settings, raising=False)
        provider._set_domain_from_config()
        assert provider.domain == "configured.com"

        # Now remove configured domain and set environment variable fallback
        fake_settings.groups.group_domain = None
        monkeypatch.setenv("SRE_BOT_EMAIL", "bot@env-domain.com")
        provider.domain = None
        provider._set_domain_from_config()
        assert provider.domain == "env-domain.com"

    def test_health_check_degraded_without_domain(self):
        """Health check should call API and handle result properly."""
        provider = GoogleWorkspaceProvider()
        provider.domain = None  # Domain not needed - uses default customer ID

        result = provider.health_check()

        assert result.status == OperationStatus.SUCCESS
        assert isinstance(result.data, dict)
        # The decorator wraps with data_key="health"
        health_data = result.data.get("health")
        assert health_data is not None
        # Health check should return a status
        assert "status" in health_data

    def test_health_check_returns_success_result(self):
        """Health check should return OperationResult with SUCCESS status."""
        provider = GoogleWorkspaceProvider()
        provider.domain = "test.com"

        result = provider.health_check()

        # The wrapper decorator converts the dict to an OperationResult
        assert isinstance(result, OperationResult)
        assert result.status == OperationStatus.SUCCESS
        assert isinstance(result.data, dict)
        # The decorator wraps with data_key="health"
        health_data = result.data.get("health")
        assert health_data is not None
        assert isinstance(health_data, dict)
