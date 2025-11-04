"""Unit tests for Google Workspace provider normalization and helper functions.

Tests cover pure unit logic extraction from GoogleWorkspaceProvider:
- Email extraction (_get_local_part)
- Group normalization (_normalize_group_from_google)
- Member normalization (_normalize_member_from_google)
- Member identifier resolution (_resolve_member_identifier)

Note: Integration tests (actual API calls) are in tests/modules/groups/providers/.
"""

import pytest
from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
from modules.groups.models import NormalizedMember, NormalizedGroup


@pytest.mark.unit
class TestGetLocalPart:
    """Test _get_local_part email extraction helper."""

    def test_get_local_part_standard_email(self):
        """Test extracting local part from standard email."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("user@example.com")
        assert result == "user"

    def test_get_local_part_with_plus_addressing(self):
        """Test extracting local part with plus addressing."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("user+tag@example.com")
        assert result == "user+tag"

    def test_get_local_part_with_dots(self):
        """Test extracting local part with dots."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("first.last@example.com")
        assert result == "first.last"

    def test_get_local_part_with_subdomain(self):
        """Test extracting local part with subdomain."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("user@mail.example.co.uk")
        assert result == "user"

    def test_get_local_part_no_at_sign(self):
        """Test with string that has no @ sign."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("notanemail")
        assert result == "notanemail"

    def test_get_local_part_empty_string(self):
        """Test with empty string."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("")
        assert result == ""

    def test_get_local_part_none(self):
        """Test with None."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part(None)
        assert result is None

    def test_get_local_part_only_at_sign(self):
        """Test with only @ sign."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("@")
        assert result == ""

    def test_get_local_part_multiple_at_signs(self):
        """Test with multiple @ signs (splits on first)."""
        provider = GoogleWorkspaceProvider()
        result = provider._get_local_part("user@domain@extra.com")
        assert result == "user"


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

    def test_normalize_member_minimal_valid(self):
        """Test that minimal member (even empty dict) validates with Pydantic."""
        provider = GoogleWorkspaceProvider()
        minimal_member = {}

        # Pydantic Member schema allows all fields Optional, so empty dict is valid
        result = provider._normalize_member_from_google(minimal_member)
        assert isinstance(result, NormalizedMember)
        assert result.email is None
        assert result.id is None

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
    """Test _resolve_member_identifier conversion."""

    def test_resolve_string_email(self):
        """Test resolving string email."""
        provider = GoogleWorkspaceProvider()
        result = provider._resolve_member_identifier("user@company.com")

        assert result == "user@company.com"

    def test_resolve_string_id(self):
        """Test resolving string ID."""
        provider = GoogleWorkspaceProvider()
        result = provider._resolve_member_identifier("member-123")

        assert result == "member-123"

    def test_resolve_string_with_whitespace(self):
        """Test that whitespace in strings is stripped."""
        provider = GoogleWorkspaceProvider()
        result = provider._resolve_member_identifier("  user@company.com  ")

        assert result == "user@company.com"

    def test_resolve_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        provider = GoogleWorkspaceProvider()

        with pytest.raises(ValueError):
            provider._resolve_member_identifier("")

    def test_resolve_dict_with_email(self):
        """Test resolving dict with email."""
        provider = GoogleWorkspaceProvider()
        member_dict = {"email": "user@company.com", "id": "member-123"}
        result = provider._resolve_member_identifier(member_dict)

        assert result == "user@company.com"

    def test_resolve_dict_with_primary_email(self):
        """Test resolving dict with primaryEmail."""
        provider = GoogleWorkspaceProvider()
        member_dict = {"primaryEmail": "user@company.com", "id": "member-123"}
        result = provider._resolve_member_identifier(member_dict)

        assert result == "user@company.com"

    def test_resolve_dict_fallback_to_id(self):
        """Test resolving dict falls back to id when email missing."""
        provider = GoogleWorkspaceProvider()
        member_dict = {"id": "member-123"}
        result = provider._resolve_member_identifier(member_dict)

        assert result == "member-123"

    def test_resolve_dict_email_precedence(self):
        """Test that email takes precedence over id."""
        provider = GoogleWorkspaceProvider()
        member_dict = {"email": "user@company.com", "id": "member-123"}
        result = provider._resolve_member_identifier(member_dict)

        assert result == "user@company.com"

    def test_resolve_dict_empty_raises(self):
        """Test that empty dict raises ValueError."""
        provider = GoogleWorkspaceProvider()

        with pytest.raises(ValueError):
            provider._resolve_member_identifier({})

    def test_resolve_normalized_member_with_email(self):
        """Test resolving NormalizedMember with email."""
        provider = GoogleWorkspaceProvider()
        member = NormalizedMember(
            email="user@company.com",
            id="member-123",
            role="MEMBER",
            provider_member_id="member-123",
        )
        result = provider._resolve_member_identifier(member)

        assert result == "user@company.com"

    def test_resolve_normalized_member_fallback_to_id(self):
        """Test resolving NormalizedMember falls back to id."""
        provider = GoogleWorkspaceProvider()
        member = NormalizedMember(
            email=None,
            id="member-123",
            role="MEMBER",
            provider_member_id="member-123",
        )
        result = provider._resolve_member_identifier(member)

        assert result == "member-123"

    def test_resolve_normalized_member_empty_raises(self):
        """Test that NormalizedMember without email or id raises."""
        provider = GoogleWorkspaceProvider()
        member = NormalizedMember(
            email=None,
            id=None,
            role="MEMBER",
            provider_member_id=None,
        )

        with pytest.raises(ValueError):
            provider._resolve_member_identifier(member)

    def test_resolve_invalid_type_raises(self):
        """Test that invalid type raises TypeError."""
        provider = GoogleWorkspaceProvider()

        with pytest.raises(TypeError):
            provider._resolve_member_identifier(123)

    def test_resolve_invalid_type_list_raises(self):
        """Test that list type raises TypeError."""
        provider = GoogleWorkspaceProvider()

        with pytest.raises(TypeError):
            provider._resolve_member_identifier(["user@company.com"])


# ============================================================================
# Integration Between Methods Tests
# ============================================================================


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
