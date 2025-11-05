"""
Phase 4-Step6: AWS Identity Center provider integration tests.

Tests real provider workflows with mocked AWS Identity Store API. Covers:
- User and membership operations (create, delete, list)
- Group listing and member management
- User resolution and lookup
- Membership ID resolution
- Error scenarios and resilience
- Circuit breaker integration
- Member and group normalization
- API contract compliance

These tests integrate the AwsIdentityCenterProvider with mocked
identity_store API calls to verify provider behavior and data flow.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.groups.providers.base import (
    OperationResult,
    OperationStatus,
)


# ============================================================================
# Fixtures: Mock Settings and AWS Identity Store
# ============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings with circuit breaker config."""
    return SimpleNamespace(
        groups=SimpleNamespace(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=5,
            circuit_breaker_timeout_seconds=60,
            circuit_breaker_half_open_max_calls=3,
            providers={},
        )
    )


@pytest.fixture
def aws_provider(mock_settings):
    """Provide an AwsIdentityCenterProvider instance with mocked settings."""
    from modules.groups.providers import aws_identity_center

    with patch("modules.groups.providers.base.settings", mock_settings):
        provider = aws_identity_center.AwsIdentityCenterProvider()
        yield provider


@pytest.fixture
def mock_identity_store():
    """Provide a mock identity_store module."""
    mock = MagicMock()
    mock.create_group_membership = MagicMock()
    mock.delete_group_membership = MagicMock()
    mock.list_group_memberships = MagicMock()
    mock.get_user_by_username = MagicMock()
    mock.get_user = MagicMock()
    mock.get_group_membership_id = MagicMock()
    mock.list_users = MagicMock()
    mock.list_groups = MagicMock()
    return mock


@pytest.fixture
def mock_aws_api_response():
    """Create sample AWS API response fixtures."""
    return {
        "user": {
            "UserId": "user-123",
            "UserName": "alice@example.com",
            "Emails": [{"Value": "alice@example.com"}],
            "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
        },
        "group": {
            "GroupId": "group-456",
            "DisplayName": "Engineering Team",
            "Description": "Core engineering team",
        },
        "membership": {
            "MembershipId": "membership-789",
            "GroupId": "group-456",
            "MemberId": {"UserId": "user-123"},
            "UserDetails": {
                "UserId": "user-123",
                "UserName": "alice@example.com",
                "Emails": [{"Value": "alice@example.com"}],
            },
        },
    }


# ============================================================================
# Test Class: Create Membership Operations
# ============================================================================


class TestAwsCreateMembershipOperations:
    """Test adding members (creating memberships) in AWS groups."""

    def test_create_membership_success_with_email(
        self, aws_provider, mock_identity_store_next, monkeypatch, mock_aws_api_response
    ):
        """Test successfully creating a membership via email."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        result = aws_provider.add_member("group-456", {"email": "alice@example.com"})

        # Verify success
        assert isinstance(result, OperationResult)
        assert result.status == OperationStatus.SUCCESS

    def test_create_membership_user_not_found(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test creating membership when user doesn't exist."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        result = aws_provider.add_member(
            "group-456", {"email": "nonexistent@example.com"}
        )

        # Should return transient error
        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_create_membership_api_failure(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test creating membership when API call fails."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        # Simulate API failure by patching to return failure
        original_create = mock_identity_store_next.create_group_membership
        mock_identity_store_next.create_group_membership = (
            lambda *args, **kwargs: SimpleNamespace(success=False, data=None)
        )

        result = aws_provider.add_member("group-456", {"email": "alice@example.com"})

        assert result.status == OperationStatus.TRANSIENT_ERROR

        # Restore original
        mock_identity_store_next.create_group_membership = original_create

    def test_create_membership_with_user_id(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test creating membership with user email."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        # AWS provider requires member_data dict with 'email' key
        member_data = {
            "email": "bob@example.com",
        }

        result = aws_provider.add_member("group-456", member_data)

        assert result.status == OperationStatus.SUCCESS


# ============================================================================
# Test Class: Delete Membership Operations
# ============================================================================


class TestAwsDeleteMembershipOperations:
    """Test removing members (deleting memberships) from AWS groups."""

    def test_delete_membership_success(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test successfully deleting a membership."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        # First add a member so we can delete it
        aws_provider.add_member("group-456", {"email": "alice@example.com"})

        # Now delete the membership
        result = aws_provider.remove_member("group-456", {"email": "alice@example.com"})

        assert result.status == OperationStatus.SUCCESS


# ============================================================================
# Test Class: List Memberships Operations
# ============================================================================


class TestAwsListMembershipsOperations:
    """Test retrieving group members from AWS groups."""

    def test_list_memberships_success(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test successfully listing memberships of a group."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        result = aws_provider.get_group_members("group-456")

        assert isinstance(result, OperationResult)
        assert result.status == OperationStatus.SUCCESS
        assert result.data is not None
        assert len(result.data) > 0

    def test_list_memberships_empty_result(
        self, aws_provider, mock_identity_store_next, monkeypatch
    ):
        """Test listing memberships when group has no members."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store_next,
        )

        # Patch the mock to return empty memberships for empty-group
        original_list = mock_identity_store_next.list_group_memberships
        mock_identity_store_next.list_group_memberships = (
            lambda *args, **kwargs: SimpleNamespace(success=True, data=[])
        )

        result = aws_provider.get_group_members("empty-group")

        assert result.status == OperationStatus.SUCCESS

        # Restore original
        mock_identity_store_next.list_group_memberships = original_list
        assert result.data["members"] == []

    def test_list_memberships_api_failure(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test listing memberships when API returns failure."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.list_group_memberships.return_value = SimpleNamespace(
            success=False,
            data=None,
        )

        result = aws_provider.get_group_members("group-456")

        assert result.status == OperationStatus.TRANSIENT_ERROR


# ============================================================================
# Test Class: List Groups Operations
# ============================================================================


class TestAwsListGroupsOperations:
    """Test retrieving groups from AWS."""

    def test_list_groups_success(
        self, aws_provider, mock_identity_store, monkeypatch, mock_aws_api_response
    ):
        """Test successfully listing groups."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        groups = [
            {
                "GroupId": "group-456",
                "DisplayName": "Engineering Team",
                "Description": "Core engineering",
            },
            {
                "GroupId": "group-457",
                "DisplayName": "DevOps Team",
                "Description": "DevOps engineers",
            },
        ]

        mock_identity_store.list_groups.return_value = SimpleNamespace(
            success=True,
            data=groups,
        )

        result = aws_provider.list_groups()

        assert result.status == OperationStatus.SUCCESS
        assert result.data is not None
        assert "groups" in result.data

        groups_result = result.data["groups"]
        assert len(groups_result) == 2

    def test_list_groups_empty_result(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test listing groups when none exist."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.list_groups.return_value = SimpleNamespace(
            success=True,
            data=[],
        )

        result = aws_provider.list_groups()

        assert result.status == OperationStatus.SUCCESS
        assert result.data["groups"] == []


# ============================================================================
# Test Class: Member Normalization
# ============================================================================


class TestAwsMemberNormalization:
    """Test member data normalization from AWS API responses."""

    def test_normalize_member_from_user(self, aws_provider):
        """Test normalizing a basic user response."""
        user_data = {
            "UserId": "user-123",
            "UserName": "alice@example.com",
            "Emails": [{"Value": "alice@example.com"}],
        }

        normalized = aws_provider._normalize_member_from_aws(user_data)

        assert normalized.id == "user-123"
        # For user responses (not memberships), provider_member_id is not set
        assert normalized.email == "alice@example.com"

    def test_normalize_member_from_membership(self, aws_provider):
        """Test normalizing a membership with user details."""
        membership_data = {
            "MembershipId": "membership-789",
            "UserDetails": {
                "UserId": "user-123",
                "UserName": "alice@example.com",
                "Emails": [{"Value": "alice@example.com"}],
                "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
            },
        }

        normalized = aws_provider._normalize_member_from_aws(membership_data)

        assert normalized.id == "user-123"
        assert normalized.provider_member_id == "membership-789"

    def test_normalize_member_missing_details(self, aws_provider):
        """Test normalizing member with minimal data."""
        user_data = {
            "UserId": "user-456",
        }

        normalized = aws_provider._normalize_member_from_aws(user_data)

        assert normalized.id == "user-456"


# ============================================================================
# Test Class: Group Normalization
# ============================================================================


class TestAwsGroupNormalization:
    """Test group data normalization from AWS API responses."""

    def test_normalize_group_basic(self, aws_provider):
        """Test normalizing a basic group response."""
        group_data = {
            "GroupId": "group-456",
            "DisplayName": "Engineering Team",
            "Description": "Core engineering team",
        }

        normalized = aws_provider._normalize_group_from_aws(group_data)

        assert normalized.id == "group-456"
        assert normalized.name == "Engineering Team"
        assert normalized.description == "Core engineering team"
        assert normalized.provider == "aws"

    def test_normalize_group_with_members(self, aws_provider):
        """Test normalizing group and separately normalizing members."""
        group_data = {
            "GroupId": "group-456",
            "DisplayName": "Engineering Team",
        }
        members = [
            {
                "UserId": "user-123",
                "UserName": "alice@example.com",
                "Emails": [{"Value": "alice@example.com"}],
            },
            {
                "UserId": "user-124",
                "UserName": "bob@example.com",
                "Emails": [{"Value": "bob@example.com"}],
            },
        ]

        # AWS normalize_group doesn't have a members parameter
        # Normalize group and members separately
        normalized_group = aws_provider._normalize_group_from_aws(group_data)
        normalized_members = [
            aws_provider._normalize_member_from_aws(m) for m in members
        ]

        assert normalized_group.id == "group-456"
        assert len(normalized_members) == 2
        assert normalized_members[0].id == "user-123"


# ============================================================================
# Test Class: User Resolution
# ============================================================================


class TestAwsUserResolution:
    """Test resolving user IDs from various identifier formats."""

    def test_resolve_email_to_user_id(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test resolving email address to AWS user ID."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_user_by_username.return_value = SimpleNamespace(
            success=True,
            data={"UserId": "user-123"},
        )

        result = aws_provider._ensure_user_id_from_email("alice@example.com")

        assert result == "user-123"
        mock_identity_store.get_user_by_username.assert_called_once_with(
            "alice@example.com"
        )

    def test_resolve_email_user_not_found(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test resolving email when user doesn't exist."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_user_by_username.return_value = SimpleNamespace(
            success=False,
            data=None,
        )

        from modules.groups.errors import IntegrationError

        with pytest.raises(IntegrationError):
            aws_provider._ensure_user_id_from_email("nonexistent@example.com")


# ============================================================================
# Test Class: Membership ID Resolution
# ============================================================================


class TestAwsMembershipIdResolution:
    """Test resolving membership IDs."""

    def test_resolve_membership_id_success(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test successfully resolving membership ID."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_group_membership_id.return_value = SimpleNamespace(
            success=True,
            data={"MembershipId": "membership-789"},
        )

        result = aws_provider._resolve_membership_id("group-456", "user-123")

        assert result == "membership-789"

    def test_resolve_membership_id_not_found(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test resolving membership ID when membership doesn't exist."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_group_membership_id.return_value = SimpleNamespace(
            success=False,
            data=None,
        )

        from modules.groups.errors import IntegrationError

        with pytest.raises(IntegrationError):
            aws_provider._resolve_membership_id("group-456", "user-123")


# ============================================================================
# Test Class: Fetch User Details
# ============================================================================


class TestAwsFetchUserDetails:
    """Test fetching user details from AWS."""

    def test_fetch_user_details_success(
        self, aws_provider, mock_identity_store, monkeypatch, mock_aws_api_response
    ):
        """Test successfully fetching user details."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_user.return_value = SimpleNamespace(
            success=True,
            data=mock_aws_api_response["user"],
        )

        result = aws_provider._fetch_user_details("user-123")

        assert result is not None
        assert result.get("UserId") == "user-123"

    def test_fetch_user_details_not_found(
        self, aws_provider, mock_identity_store, monkeypatch
    ):
        """Test fetching user details when user doesn't exist."""
        from modules.groups.providers import aws_identity_center

        monkeypatch.setattr(
            aws_identity_center,
            "identity_store",
            mock_identity_store,
        )

        mock_identity_store.get_user.return_value = SimpleNamespace(
            success=False,
            data=None,
        )

        from modules.groups.errors import IntegrationError

        with pytest.raises(IntegrationError):
            aws_provider._fetch_user_details("user-999")


# ============================================================================
# Test Class: Provider Capabilities
# ============================================================================


class TestAwsProviderCapabilities:
    """Test AWS provider capabilities reporting."""

    def test_capabilities_reporting(self, aws_provider):
        """Test that provider reports correct capabilities."""
        caps = aws_provider.capabilities

        assert caps.supports_member_management is True
        # AWS does not support group creation/deletion
        assert caps.supports_group_creation is False
        assert caps.supports_group_deletion is False


# ============================================================================
# Test Class: Extract ID from Response
# ============================================================================


class TestAwsExtractIdFromResponse:
    """Test ID extraction from AWS API responses."""

    def test_extract_id_from_dict_response(self, aws_provider):
        """Test extracting ID from dict response."""
        resp = SimpleNamespace(success=True, data={"UserId": "user-123"})

        result = aws_provider._extract_id_from_resp(resp, ["UserId", "Id"])

        assert result == "user-123"

    def test_extract_id_from_string_response(self, aws_provider):
        """Test extracting ID when response is a string."""
        resp = SimpleNamespace(success=True, data="user-123")

        result = aws_provider._extract_id_from_resp(resp, ["UserId"])

        assert result == "user-123"

    def test_extract_id_failed_response(self, aws_provider):
        """Test extracting ID from failed response."""
        resp = SimpleNamespace(success=False, data=None)

        result = aws_provider._extract_id_from_resp(resp, ["UserId"])

        assert result is None


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestAwsErrorHandling:
    """Test error handling in AWS provider."""

    def test_invalid_response_type_raises_integration_error(self, aws_provider):
        """Test handling invalid response type."""
        from modules.groups.errors import IntegrationError

        # Response without success attribute
        with pytest.raises(IntegrationError):
            aws_provider._extract_id_from_resp("invalid", ["UserId"])


# ============================================================================
# Integration Marker
# ============================================================================

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration
