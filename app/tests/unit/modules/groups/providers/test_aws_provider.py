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
from modules.groups.providers.base import OperationResult, OperationStatus


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

    def test_get_group_members_handles_missing_user_details(self, monkeypatch):
        provider = AwsIdentityCenterProvider()

        # Mock list_group_memberships to return memberships without MemberId
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.list_group_memberships",
            lambda gid: types.SimpleNamespace(
                success=True, data=[{"MembershipId": "m-1"}]
            ),
            raising=False,
        )

        # Mock get_group_by_name to return a valid id so _resolve_group_id won't fail
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            lambda name: types.SimpleNamespace(
                success=True, data={"GroupId": "group-1"}
            ),
            raising=False,
        )

        # Mock get_user to raise IntegrationError to simulate missing details
        def fake_get_user(uid):
            return types.SimpleNamespace(success=False, data=None)

        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user",
            fake_get_user,
            raising=False,
        )

        res = provider._get_group_members_impl("group-1")
        # Decorator wraps result in OperationResult; inspect .data
        assert isinstance(res, OperationResult)
        members = res.data.get("members")
        assert isinstance(members, list)
        assert len(members) == 1

    def test_add_member_raises_when_missing_identity_methods(self, monkeypatch):
        provider = AwsIdentityCenterProvider()

        # Ensure resolve_group_id returns the input UUID (simulate already-id)
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            None,
            raising=False,
        )

        # Remove get_user_by_username to trigger IntegrationError in _ensure_user_id_from_email
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user_by_username",
            None,
            raising=False,
        )

        res = provider._add_member_impl("group-1", {"email": "user@x"})
        # opresult_wrapper catches exceptions and returns a transient error
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.TRANSIENT_ERROR

    def test_add_member_success_returns_normalized_member(self, monkeypatch):
        """Simulate successful add: identity_store methods return success and provider returns normalized member."""
        provider = AwsIdentityCenterProvider()

        # Simulate _resolve_group_id returning the group id directly by having
        # get_group_by_name return a successful result with GroupId
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            lambda name: types.SimpleNamespace(
                success=True, data={"GroupId": "group-1"}
            ),
            raising=False,
        )

        # Simulate get_user_by_username returning user id
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user_by_username",
            lambda email: types.SimpleNamespace(
                success=True, data={"UserId": "user-1"}
            ),
            raising=False,
        )

        # Simulate create_group_membership success
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.create_group_membership",
            lambda gid, uid: types.SimpleNamespace(
                success=True, data={"MembershipId": "m-1"}
            ),
            raising=False,
        )

        # Simulate get_user returning full details
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user",
            lambda uid: types.SimpleNamespace(
                success=True,
                data={
                    "UserId": "user-1",
                    "Emails": [{"Value": "alice@example.com"}],
                    "Name": {"GivenName": "Alice", "FamilyName": "Example"},
                },
            ),
            raising=False,
        )

        res = provider._add_member_impl("my-group", {"email": "alice@example.com"})
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.SUCCESS
        member = res.data.get("result")
        assert member is not None
        # The normalizer may not populate all fields for this combined path.
        # Ensure we received a canonical member dict with expected keys.
        assert isinstance(member, dict)
        assert "id" in member
        assert "email" in member

    def test_remove_member_success_returns_normalized_member(self, monkeypatch):
        """Simulate successful remove: identity_store methods return success and provider returns normalized member."""
        provider = AwsIdentityCenterProvider()

        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_by_name",
            lambda name: types.SimpleNamespace(
                success=True, data={"GroupId": "group-1"}
            ),
            raising=False,
        )

        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user_by_username",
            lambda email: types.SimpleNamespace(
                success=True, data={"UserId": "user-1"}
            ),
            raising=False,
        )

        # Simulate resolve membership id
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_group_membership_id",
            lambda gid, uid: types.SimpleNamespace(
                success=True, data={"MembershipId": "m-1"}
            ),
            raising=False,
        )

        # Simulate delete_group_membership success
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.delete_group_membership",
            lambda membership_id: types.SimpleNamespace(success=True, data={}),
            raising=False,
        )

        # Simulate get_user returning full details
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.get_user",
            lambda uid: types.SimpleNamespace(
                success=True,
                data={
                    "UserId": "user-1",
                    "Emails": [{"Value": "bob@example.com"}],
                    "Name": {"GivenName": "Bob", "FamilyName": "Builder"},
                },
            ),
            raising=False,
        )

        res = provider._remove_member_impl("my-group", {"email": "bob@example.com"})
        assert isinstance(res, OperationResult)
        assert res.status == OperationStatus.SUCCESS
        member = res.data.get("result")
        assert member is not None
        assert isinstance(member, dict)
        assert "id" in member
        assert "email" in member

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

    def test_list_groups_returns_empty_pages(self, monkeypatch):
        """Simulate list_groups returning empty pages (no groups)."""
        provider = AwsIdentityCenterProvider()

        # identity_store.list_groups returns OperationResult-like object
        monkeypatch.setattr(
            "integrations.aws.identity_store_next.list_groups",
            lambda **kw: types.SimpleNamespace(success=True, data=[]),
            raising=False,
        )

        res = provider._list_groups_impl()
        assert isinstance(res, OperationResult)
        groups = res.data.get("groups")
        assert groups == []

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
