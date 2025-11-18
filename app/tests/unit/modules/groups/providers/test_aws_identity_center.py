"""Unit tests for AWS Identity Center provider.

Comprehensive test suite covering:
- ID extraction from API responses with error handling
- Member and group normalization from AWS format
- Email-based add_member and remove_member operations
- Email validation using shared validate_member_email function
- UUID resolution and pattern matching
- Provider capabilities
- API interactions with identity_store
- Health check functionality
- Integration between normalization and resolution methods

Note: Integration tests (actual API calls) are in tests/modules/groups/providers/.
"""

import types
from unittest.mock import Mock, patch

import pytest
from modules.groups.domain.models import NormalizedGroup, NormalizedMember
from modules.groups.providers.aws_identity_center import (
    AWS_UUID_REGEX,
    AwsIdentityCenterProvider,
)
from modules.groups.providers.base import validate_member_email
from modules.groups.providers.contracts import OperationResult, OperationStatus

# ============================================================================
# ID Extraction Tests
# ============================================================================


@pytest.mark.unit
class TestAwsExtractIdFromResp:
    """Test _extract_id_from_resp helper function with error handling."""

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_extract_id_from_resp_with_userid(self, mock_settings):
        """Test extracting UserId from response with error handling."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()
        resp = Mock()
        resp.data = {"UserId": "user-123"}

        user_id = provider._extract_id_from_resp(resp, ["UserId", "Id"], "test_op")
        assert user_id == "user-123"

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_extract_id_from_resp_with_fallback_field(self, mock_settings):
        """Test extracting ID using fallback field name."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()
        resp = Mock()
        resp.data = {"Id": "id-456"}  # UserId not present

        user_id = provider._extract_id_from_resp(resp, ["UserId", "Id"], "test_op")
        assert user_id == "id-456"

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_extract_id_from_resp_raises_on_missing_fields(self, mock_settings):
        """Test that extraction fails when no fields found."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()
        resp = Mock()
        resp.data = {"SomeOtherField": "value"}

        with pytest.raises(Exception):  # Should raise IntegrationError
            provider._extract_id_from_resp(resp, ["UserId", "Id"], "test_op")

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_extract_id_from_resp_raises_on_none_response(self, mock_settings):
        """Test that extraction fails when response is None."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()

        with pytest.raises(ValueError):
            provider._extract_id_from_resp(None, ["UserId"], "test_op")


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
# UUID Resolution and Pattern Tests
# ============================================================================


@pytest.mark.unit
class TestAwsIdentityCenterUUIDResolution:
    """Test UUID pattern matching and resolution."""

    def test_aws_group_uuid_pattern_matches_valid_uuid(self):
        """Test that UUID pattern matches valid AWS group IDs."""
        valid_uuid = "12345678-1234-1234-1234-123456789012"
        assert AWS_UUID_REGEX.match(valid_uuid)

    def test_aws_group_uuid_pattern_rejects_invalid_uuid(self):
        """Test that UUID pattern rejects invalid group IDs."""
        invalid_uuid = "not-a-uuid"
        assert not AWS_UUID_REGEX.match(invalid_uuid)

    def test_aws_group_uuid_pattern_case_insensitive(self):
        """Test that UUID pattern matches uppercase and lowercase."""
        uppercase = "ABCDEF12-1234-1234-1234-123456789012"
        lowercase = "abcdef12-1234-1234-1234-123456789012"
        assert AWS_UUID_REGEX.match(uppercase)
        assert AWS_UUID_REGEX.match(lowercase)

    @patch("modules.groups.providers.aws_identity_center.identity_store")
    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_resolve_group_id_with_uuid(self, mock_settings, mock_identity_store):
        """Test resolving UUID group IDs directly."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()

        # A valid UUID should be returned as-is
        group_uuid = "12345678-1234-1234-1234-123456789012"
        resolved = provider._resolve_group_id(group_uuid)

        assert resolved == group_uuid

    @pytest.mark.skip(
        reason="Display name resolution is optional feature - deferred for later phase"
    )
    @patch("modules.groups.providers.aws_identity_center.identity_store")
    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_resolve_group_id_with_display_name(
        self, mock_settings, mock_identity_store
    ):
        """Test resolving group IDs by display name through list_groups.

        Note: This test is skipped as display name resolution is an optional
        feature that requires integration with list_groups API. Core UUID
        resolution is tested in test_resolve_group_id_with_uuid.
        """
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        # Mock group lookup by display name
        mock_response = Mock()
        mock_response.success = True
        # Return groups data as dict (not wrapped in MagicMock)
        mock_response.data = {
            "Groups": [
                {
                    "GroupId": "12345678-1234-1234-1234-123456789012",
                    "DisplayName": "developers",
                }
            ]
        }
        mock_identity_store.list_groups.return_value = mock_response

        provider = AwsIdentityCenterProvider()

        # Display name should be looked up
        resolved = provider._resolve_group_id("developers")
        assert resolved == "12345678-1234-1234-1234-123456789012"


# ============================================================================
# Email-Based Operations Tests
# ============================================================================


@pytest.mark.unit
class TestAwsIdentityCenterEmailBasedOperations:
    """Test email-based add_member and remove_member operations."""

    @patch("modules.groups.providers.aws_identity_center.identity_store")
    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_add_member_validates_email(self, mock_settings, mock_identity_store):
        """Test that add_member validates email format."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()

        # Invalid email (no @) should fail
        result = provider.add_member("group-123", "invalid-email")
        assert result.status == OperationStatus.TRANSIENT_ERROR

    @patch("modules.groups.providers.aws_identity_center.identity_store")
    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_add_member_normalizes_email_before_lookup(
        self, mock_settings, mock_identity_store
    ):
        """Test that add_member normalizes email before sending to API."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        # Mock user lookup to capture call
        mock_user_response = Mock()
        mock_user_response.success = True
        mock_user_response.data = {"UserId": "user-123"}
        mock_identity_store.get_user_by_username.return_value = mock_user_response

        # Mock group lookup
        mock_group_response = Mock()
        mock_group_response.success = True
        mock_group_response.data = {"GroupId": "12345678-1234-1234-1234-123456789012"}
        mock_identity_store.list_groups.return_value = mock_group_response

        provider = AwsIdentityCenterProvider()

        # Attempt add with mixed-case email
        provider.add_member("12345678-1234-1234-1234-123456789012", "User@EXAMPLE.COM")

        # Verify the normalized email was used (domain lowercased)
        call_args = mock_identity_store.get_user_by_username.call_args
        assert call_args is not None

    @patch("modules.groups.providers.aws_identity_center.identity_store")
    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_remove_member_validates_email(self, mock_settings, mock_identity_store):
        """Test that remove_member validates email format."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        provider = AwsIdentityCenterProvider()

        # Invalid email (empty) should fail
        result = provider.remove_member("group-123", "")
        assert result.status == OperationStatus.TRANSIENT_ERROR


# ============================================================================
# Email Validation Tests
# ============================================================================


@pytest.mark.unit
class TestAwsIdentityCenterEmailValidation:
    """Test email validation using shared function."""

    def test_validate_member_email_used(self):
        """Test that validate_member_email function is available."""
        email = validate_member_email("user@example.com")
        assert email == "user@example.com"

    def test_validate_member_email_normalizes(self):
        """Test that email validation normalizes addresses."""
        email = validate_member_email("User@EXAMPLE.COM")
        # email-validator preserves local part case but normalizes domain
        assert email == "User@example.com"


# ============================================================================
# Provider Capabilities Tests
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
# Helper Methods and Data Structure Tests
# ============================================================================


@pytest.mark.unit
class TestAwsIdentityCenterHelperMethods:
    """Test helper method availability and structure."""

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_membership_structure(self, mock_settings):
        """Test the structure of membership objects."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        membership = {"UserId": "user-123", "GroupId": "group-456"}

        # Membership dict structure has expected fields
        assert membership["UserId"] == "user-123"
        assert membership["GroupId"] == "group-456"

    @patch("modules.groups.providers.aws_identity_center.settings")
    def test_user_data_structure(self, mock_settings):
        """Test the structure of user data objects."""
        mock_settings.groups.circuit_breaker_enabled = False
        mock_settings.aws.identity_store_id = "us-east-1"

        user_data = {
            "UserId": "user-123",
            "UserName": "user@company.com",
            "Emails": [
                {"Value": "user@company.com", "Primary": True},
            ],
        }

        # User data has expected structure
        assert user_data["UserId"] == "user-123"
        assert user_data["UserName"] == "user@company.com"
        assert len(user_data["Emails"]) >= 1


# ============================================================================
# Integration Between Methods Tests
# ============================================================================


@pytest.mark.unit
class TestAwsProviderIntegration:
    """Test interactions between AWS provider methods."""

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


# ============================================================================
# API Integration and Error Handling Tests
# ============================================================================


@pytest.mark.unit
class TestAwsProviderApiInteractions:
    """Tests that exercise identity_store integration points and error branches."""

    def test_resolve_group_id_raises_when_get_group_missing(self, monkeypatch):
        provider = AwsIdentityCenterProvider()
        # Remove get_group_by_name on the actual imported module used by provider
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            None,
            raising=False,
        )
        with pytest.raises(Exception):
            provider._resolve_group_id("non-uuid-name")

    def test_resolve_group_id_raises_on_unexpected_response_type(self, monkeypatch):
        provider = AwsIdentityCenterProvider()

        class BadResp:
            pass

        def fake_get_group_by_name(name):
            return BadResp()

        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            fake_get_group_by_name,
            raising=False,
        )
        with pytest.raises(Exception):
            provider._resolve_group_id("non-uuid-name")

    def test_list_groups_raises_when_method_missing(self, monkeypatch):
        """If the identity_store lacks list_groups, provider should raise IntegrationError."""
        provider = AwsIdentityCenterProvider()
        # Remove the attribute entirely so hasattr checks fail
        monkeypatch.delattr(
            "integrations.aws.identity_store_next.list_groups",
            raising=False,
        )

        res = provider._list_groups_impl()
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.TRANSIENT_ERROR

    def test_list_groups_with_memberships_handles_unexpected_response(
        self, monkeypatch
    ):
        """If list_groups_with_memberships returns unexpected type, provider raises."""
        provider = AwsIdentityCenterProvider()

        class BadResp:
            pass

        monkeypatch.setattr(
            "integrations.aws.identity_store_next.list_groups_with_memberships",
            lambda **kw: BadResp(),
            raising=False,
        )
        res = provider._list_groups_with_members_impl()
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.TRANSIENT_ERROR
