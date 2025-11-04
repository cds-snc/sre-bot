"""Unit tests for AWS Identity Center provider normalization and helper functions.

Tests cover pure unit logic extraction from AwsIdentityCenterProvider:
- Member normalization (_normalize_member_from_aws)
- Group normalization (_normalize_group_from_aws)
- Member identifier resolution (_resolve_member_identifier)
- ID extraction (_extract_id_from_resp)

Note: Integration tests (actual API calls) are in tests/modules/groups/providers/.
"""

import pytest
import types
from modules.groups.providers.aws_identity_center import AwsIdentityCenterProvider
from modules.groups.models import NormalizedMember, NormalizedGroup


@pytest.mark.unit
class TestAwsExtractIdFromResp:
    """Test _extract_id_from_resp helper function."""

    def test_extract_id_from_string_response(self):
        """Test extracting ID from string response."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(success=True, data="user-123")
        result = provider._extract_id_from_resp(resp, ["UserId"])
        assert result == "user-123"

    def test_extract_id_from_dict_response_first_key(self):
        """Test extracting ID from dict using first available key."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(success=True, data={"UserId": "user-123"})
        result = provider._extract_id_from_resp(resp, ["UserId", "Id"])
        assert result == "user-123"

    def test_extract_id_from_dict_response_fallback_key(self):
        """Test extracting ID falling back to second key."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(success=True, data={"Id": "group-456"})
        result = provider._extract_id_from_resp(resp, ["UserId", "Id"])
        assert result == "group-456"

    def test_extract_id_from_nested_member_id(self):
        """Test extracting ID from nested MemberId dict."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(
            success=True,
            data={"MemberId": {"UserId": "user-123"}},
        )
        result = provider._extract_id_from_resp(resp, [])
        assert result == "user-123"

    def test_extract_id_from_none_response(self):
        """Test extracting ID from None response."""
        provider = AwsIdentityCenterProvider()
        result = provider._extract_id_from_resp(None, ["UserId"])
        assert result is None

    def test_extract_id_from_failed_response(self):
        """Test extracting ID from failed response."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(success=False, data={})
        result = provider._extract_id_from_resp(resp, ["UserId"])
        assert result is None

    def test_extract_id_from_dict_missing_all_keys(self):
        """Test extracting ID when all keys missing."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(success=True, data={"OtherId": "123"})
        result = provider._extract_id_from_resp(resp, ["UserId", "Id"])
        assert result is None


# ============================================================================
# Member Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestAwsNormalizeMemberFromAws:
    """Test _normalize_member_from_aws conversion."""

    def test_normalize_aws_user_basic(self):
        """Test normalizing basic AWS user."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
        }
        result = provider._normalize_member_from_aws(aws_user)

        assert isinstance(result, NormalizedMember)
        assert result.id == "user-123"
        assert result.email == "john@company.com"

    def test_normalize_aws_user_with_name(self):
        """Test normalizing AWS user with name."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
            "Name": {
                "GivenName": "John",
                "FamilyName": "Doe",
            },
        }
        result = provider._normalize_member_from_aws(aws_user)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_aws_user_strips_name_whitespace(self):
        """Test that names are stripped of whitespace."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
            "Name": {
                "GivenName": "  John  ",
                "FamilyName": "  Doe  ",
            },
        }
        result = provider._normalize_member_from_aws(aws_user)

        assert result.first_name == "John"
        assert result.family_name == "Doe"

    def test_normalize_aws_user_no_email(self):
        """Test normalizing AWS user without email."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
        }
        result = provider._normalize_member_from_aws(aws_user)

        assert result.email is None
        assert result.id == "user-123"

    def test_normalize_aws_user_empty_emails_list(self):
        """Test normalizing AWS user with empty emails list."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [],
        }
        result = provider._normalize_member_from_aws(aws_user)

        assert result.email is None

    def test_normalize_aws_group_membership(self):
        """Test normalizing AWS group membership."""
        provider = AwsIdentityCenterProvider()
        membership_data = {
            "MembershipId": "membership-123",
            "GroupId": "group-456",
            "MemberId": {"UserId": "member-789"},
            "UserDetails": {
                "UserId": "user-123",
                "UserName": "john.doe",
                "Emails": [{"Value": "john@company.com"}],
            },
        }
        result = provider._normalize_member_from_aws(membership_data)

        assert result.provider_member_id == "membership-123"
        assert result.email == "john@company.com"
        assert result.id == "user-123"

    def test_normalize_aws_user_with_raw_data(self):
        """Test that raw data is stored when requested."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
        }
        result = provider._normalize_member_from_aws(aws_user, include_raw=True)

        assert result.raw == aws_user

    def test_normalize_aws_user_without_raw_data(self):
        """Test that raw data is None when not requested."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
        }
        result = provider._normalize_member_from_aws(aws_user, include_raw=False)

        assert result.raw is None


# ============================================================================
# Group Normalization Tests
# ============================================================================


@pytest.mark.unit
class TestAwsNormalizeGroupFromAws:
    """Test _normalize_group_from_aws conversion."""

    def test_normalize_aws_group_basic(self):
        """Test normalizing basic AWS group."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
            "Description": "Development team",
        }
        result = provider._normalize_group_from_aws(aws_group)

        assert isinstance(result, NormalizedGroup)
        assert result.id == "group-123"
        assert result.name == "Developers"
        assert result.description == "Development team"
        assert result.provider == "aws"

    def test_normalize_aws_group_fallback_to_id_for_name(self):
        """Test that GroupId is used if DisplayName missing."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
        }
        result = provider._normalize_group_from_aws(aws_group)

        assert result.id == "group-123"
        assert result.name == "group-123"

    def test_normalize_aws_group_with_memberships(self):
        """Test normalizing group with memberships."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        memberships = [
            {
                "MembershipId": "membership-1",
                "UserDetails": {
                    "UserId": "user-1",
                    "Emails": [{"Value": "user1@company.com"}],
                },
            },
            {
                "MembershipId": "membership-2",
                "UserDetails": {
                    "UserId": "user-2",
                    "Emails": [{"Value": "user2@company.com"}],
                },
            },
        ]
        result = provider._normalize_group_from_aws(aws_group, memberships=memberships)

        assert len(result.members) == 2
        assert result.members[0].email == "user1@company.com"
        assert result.members[1].email == "user2@company.com"

    def test_normalize_aws_group_from_group_dict_memberships_fallback(self):
        """Test that memberships from group dict are used as fallback."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
            "GroupMemberships": [
                {
                    "MembershipId": "membership-1",
                    "UserDetails": {
                        "UserId": "user-1",
                        "Emails": [{"Value": "user1@company.com"}],
                    },
                },
            ],
        }
        result = provider._normalize_group_from_aws(aws_group)

        assert len(result.members) == 1
        assert result.members[0].email == "user1@company.com"

    def test_normalize_aws_group_filters_non_dict_memberships(self):
        """Test that non-dict memberships are filtered out."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        memberships = [
            {
                "MembershipId": "membership-1",
                "UserDetails": {
                    "UserId": "user-1",
                    "Emails": [{"Value": "user1@company.com"}],
                },
            },
            "invalid",  # Should be filtered
            None,  # Should be filtered
        ]
        result = provider._normalize_group_from_aws(aws_group, memberships=memberships)

        assert len(result.members) == 1

    def test_normalize_aws_group_with_raw_data(self):
        """Test that raw data is stored when requested."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        result = provider._normalize_group_from_aws(aws_group, include_raw=True)

        assert result.raw == aws_group

    def test_normalize_aws_group_without_raw_data(self):
        """Test that raw data is None when not requested."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        result = provider._normalize_group_from_aws(aws_group, include_raw=False)

        assert result.raw is None

    def test_normalize_aws_group_no_description(self):
        """Test normalizing group without description."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        result = provider._normalize_group_from_aws(aws_group)

        assert result.description is None


# ============================================================================
# Member Identifier Resolution Tests
# ============================================================================


@pytest.mark.unit
class TestAwsResolveMemberIdentifier:
    """Test _resolve_member_identifier conversion."""

    def test_resolve_string_email(self):
        """Test resolving string email."""
        provider = AwsIdentityCenterProvider()
        result = provider._resolve_member_identifier("user@company.com")

        assert result == "user@company.com"

    def test_resolve_string_with_whitespace(self):
        """Test that whitespace in strings is stripped."""
        provider = AwsIdentityCenterProvider()
        result = provider._resolve_member_identifier("  user@company.com  ")

        assert result == "user@company.com"

    def test_resolve_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        provider = AwsIdentityCenterProvider()

        with pytest.raises(ValueError):
            provider._resolve_member_identifier("")

    def test_resolve_dict_with_email(self):
        """Test resolving dict with email."""
        provider = AwsIdentityCenterProvider()
        member_dict = {"email": "user@company.com", "id": "user-123"}
        result = provider._resolve_member_identifier(member_dict)

        assert result == "user@company.com"

    def test_resolve_dict_missing_email_raises(self):
        """Test that dict without email raises ValueError."""
        provider = AwsIdentityCenterProvider()
        member_dict = {"id": "user-123"}

        with pytest.raises(ValueError):
            provider._resolve_member_identifier(member_dict)

    def test_resolve_dict_empty_raises(self):
        """Test that empty dict raises ValueError."""
        provider = AwsIdentityCenterProvider()

        with pytest.raises(ValueError):
            provider._resolve_member_identifier({})

    def test_resolve_invalid_type_raises(self):
        """Test that invalid type raises TypeError."""
        provider = AwsIdentityCenterProvider()

        with pytest.raises(TypeError):
            provider._resolve_member_identifier(123)

    def test_resolve_invalid_type_list_raises(self):
        """Test that list type raises TypeError."""
        provider = AwsIdentityCenterProvider()

        with pytest.raises(TypeError):
            provider._resolve_member_identifier(["user@company.com"])


# ============================================================================
# AWS Provider Capabilities Tests
# ============================================================================


@pytest.mark.unit
class TestAwsProviderCapabilities:
    """Test AWS provider capabilities."""

    def test_capabilities_supports_member_management(self):
        """Test that AWS provider supports member management."""
        provider = AwsIdentityCenterProvider()
        caps = provider.capabilities

        assert caps.supports_member_management is True

    def test_capabilities_not_primary(self):
        """Test that AWS provider is not primary."""
        provider = AwsIdentityCenterProvider()
        caps = provider.capabilities

        assert caps.is_primary is False

    def test_capabilities_defaults(self):
        """Test default AWS provider capabilities."""
        provider = AwsIdentityCenterProvider()
        caps = provider.capabilities

        assert caps.supports_user_creation is False
        assert caps.supports_user_deletion is False
        assert caps.supports_group_creation is False
        assert caps.supports_group_deletion is False
        assert caps.supports_batch_operations is False
        assert caps.provides_role_info is False


# ============================================================================
# Integration Between Methods Tests
# ============================================================================


@pytest.mark.unit
class TestAwsProviderIntegration:
    """Test interactions between AWS provider methods."""

    def test_normalize_user_then_resolve_identifier(self):
        """Test normalizing a user then resolving identifier."""
        provider = AwsIdentityCenterProvider()
        aws_user = {
            "UserId": "user-123",
            "UserName": "john.doe",
            "Emails": [{"Value": "john@company.com"}],
        }
        normalized = provider._normalize_member_from_aws(aws_user)
        resolved = provider._resolve_member_identifier({"email": normalized.email})

        assert resolved == "john@company.com"

    def test_group_with_normalized_members(self):
        """Test group normalization maintains member normalization."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Developers",
        }
        memberships = [
            {
                "MembershipId": "membership-1",
                "UserDetails": {
                    "UserId": "user-1",
                    "Emails": [{"Value": "john@company.com"}],
                    "Name": {
                        "GivenName": "John",
                        "FamilyName": "Doe",
                    },
                },
            },
        ]
        result = provider._normalize_group_from_aws(aws_group, memberships=memberships)

        assert result.members[0].first_name == "John"
        assert result.members[0].email == "john@company.com"

    def test_extract_id_used_in_member_normalization(self):
        """Test that ID extraction logic applies to normalized members."""
        provider = AwsIdentityCenterProvider()
        resp = types.SimpleNamespace(
            success=True,
            data={
                "UserId": "user-123",
                "UserName": "john.doe",
                "Emails": [{"Value": "john@company.com"}],
            },
        )
        user_id = provider._extract_id_from_resp(resp, ["UserId", "Id"])
        assert user_id == "user-123"

        # Now normalize using that response data
        normalized = provider._normalize_member_from_aws(resp.data)
        assert normalized.id == user_id

    def test_aws_group_with_multiple_membership_types(self):
        """Test group with different membership scenarios."""
        provider = AwsIdentityCenterProvider()
        aws_group = {
            "GroupId": "group-123",
            "DisplayName": "Mixed Team",
        }
        memberships = [
            {
                "MembershipId": "membership-1",
                "UserDetails": {
                    "UserId": "user-1",
                    "Emails": [{"Value": "user1@company.com"}],
                    "Name": {"GivenName": "User", "FamilyName": "One"},
                },
            },
            {
                "MembershipId": "membership-2",
                "UserDetails": {
                    "UserId": "user-2",
                    "Emails": [{"Value": "user2@company.com"}],
                },
            },
        ]
        result = provider._normalize_group_from_aws(aws_group, memberships=memberships)

        assert len(result.members) == 2
        assert result.members[0].first_name == "User"
        assert result.members[0].family_name == "One"
        assert result.members[1].first_name is None
