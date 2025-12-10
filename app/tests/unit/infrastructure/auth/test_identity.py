"""Unit tests for infrastructure.auth.identity module.

Tests cover:
- UserIdentity dataclass creation
- IdentitySource enum values
- IdentityResolver resolution methods
"""

import pytest
from unittest.mock import Mock
from infrastructure.auth.identity import (
    UserIdentity,
    IdentitySource,
    IdentityResolver,
    identity_resolver,
)


class TestUserIdentity:
    """Test suite for UserIdentity dataclass."""

    def test_user_identity_creation(self):
        """Test UserIdentity can be created with all fields."""
        identity = UserIdentity(
            user_id="user123",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            permissions=["read", "write"],
            metadata={"team": "engineering"},
        )

        assert identity.user_id == "user123"
        assert identity.email == "test@example.com"
        assert identity.display_name == "Test User"
        assert identity.source == IdentitySource.SLACK
        assert identity.platform_id == "U123ABC"
        assert identity.permissions == ["read", "write"]
        assert identity.metadata == {"team": "engineering"}

    def test_user_identity_empty_lists_dicts(self):
        """Test UserIdentity handles empty permissions and metadata."""
        identity = UserIdentity(
            user_id="user123",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SYSTEM,
            platform_id="system",
            permissions=[],
            metadata={},
        )

        assert identity.permissions == []
        assert identity.metadata == {}


class TestIdentitySource:
    """Test suite for IdentitySource enum."""

    def test_identity_source_values(self):
        """Test IdentitySource enum has expected values."""
        assert IdentitySource.SLACK.value == "slack"
        assert IdentitySource.API_JWT.value == "api_jwt"
        assert IdentitySource.WEBHOOK.value == "webhook"
        assert IdentitySource.SYSTEM.value == "system"

    def test_identity_source_from_string(self):
        """Test IdentitySource can be created from string."""
        source = IdentitySource("slack")
        assert source == IdentitySource.SLACK


class TestIdentityResolver:
    """Test suite for IdentityResolver class."""

    def test_identity_resolver_initialization(self):
        """Test IdentityResolver can be instantiated."""
        resolver = IdentityResolver()
        assert resolver is not None

    @pytest.mark.skip(reason="Requires mocking SlackClientManager properly")
    def test_resolve_from_slack_with_valid_user(self):
        """Test resolve_from_slack with valid Slack user."""
        resolver = IdentityResolver()

        # Mock SlackClientManager
        mock_slack = Mock()
        mock_slack.get_user_info.return_value = {
            "user": {
                "id": "U123ABC",
                "profile": {
                    "email": "test@example.com",
                    "display_name": "Test User",
                    "real_name": "Test User",
                },
            }
        }
        resolver.slack_client = mock_slack

        identity = resolver.resolve_from_slack("U123ABC")

        assert identity.user_id == "test@example.com"
        assert identity.email == "test@example.com"
        assert identity.display_name == "Test User"
        assert identity.source == IdentitySource.SLACK
        assert identity.platform_id == "U123ABC"

    @pytest.mark.skip(reason="Requires mocking SlackClientManager properly")
    def test_resolve_from_slack_missing_user(self):
        """Test resolve_from_slack with non-existent user."""
        resolver = IdentityResolver()

        mock_slack = Mock()
        mock_slack.get_user_info.return_value = None
        resolver.slack_client = mock_slack

        identity = resolver.resolve_from_slack("INVALID")

        assert identity is None

    def test_resolve_from_jwt_with_valid_token(self):
        """Test resolve_from_jwt with valid JWT claims."""
        resolver = IdentityResolver()

        jwt_claims = {
            "sub": "user123",
            "email": "jwt@example.com",
            "name": "JWT User",
            "permissions": ["admin"],
        }

        identity = resolver.resolve_from_jwt(jwt_claims)

        assert identity.user_id == "user123"
        assert identity.email == "jwt@example.com"
        assert identity.display_name == "JWT User"
        assert identity.source == IdentitySource.API_JWT
        assert identity.platform_id == "user123"
        assert identity.permissions == ["admin"]

    def test_resolve_from_jwt_missing_fields(self):
        """Test resolve_from_jwt with minimal JWT claims."""
        resolver = IdentityResolver()

        jwt_claims = {
            "sub": "user456",
        }

        identity = resolver.resolve_from_jwt(jwt_claims)

        assert identity.user_id == "user456"
        assert identity.email == "unknown"
        assert identity.display_name == "user456"
        assert identity.permissions == []

    def test_resolve_from_webhook_with_payload(self):
        """Test resolve_from_webhook with webhook payload."""
        resolver = IdentityResolver()

        webhook_payload = {
            "user_id": "webhook_user",
            "email": "webhook@example.com",
            "name": "Webhook User",
        }

        identity = resolver.resolve_from_webhook(webhook_payload, "github")

        assert identity.user_id == "webhook_user"
        assert identity.email == "webhook@example.com"
        assert identity.display_name == "Webhook User"
        assert identity.source == IdentitySource.WEBHOOK
        assert identity.metadata["webhook_source"] == "github"


@pytest.mark.unit
class TestIdentityResolverSingleton:
    """Test suite for identity_resolver singleton."""

    def test_identity_resolver_singleton_exists(self):
        """Test identity_resolver singleton is available."""
        assert identity_resolver is not None
        assert isinstance(identity_resolver, IdentityResolver)

    def test_identity_resolver_singleton_consistent(self):
        """Test identity_resolver returns same instance."""
        from infrastructure.auth import identity_resolver as resolver2

        assert identity_resolver is resolver2
