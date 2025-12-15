"""Tests for infrastructure.identity.resolver module."""

import pytest
from unittest.mock import Mock

from infrastructure.identity.resolver import IdentityResolver
from infrastructure.identity.models import IdentitySource, User, SlackUser


class TestIdentityResolverInitialization:
    """Test suite for IdentityResolver initialization."""

    def test_identity_resolver_creation_without_slack(self):
        """Test IdentityResolver can be created without Slack client."""
        resolver = IdentityResolver()
        assert resolver is not None

    def test_identity_resolver_creation_with_slack(self):
        """Test IdentityResolver can be created with Slack client manager."""
        mock_slack = Mock()
        resolver = IdentityResolver(slack_client_manager=mock_slack)
        assert resolver is not None
        assert resolver._slack_client_manager == mock_slack


class TestResolveFromJWT:
    """Test suite for JWT resolution."""

    def test_resolve_from_jwt_with_all_claims(self):
        """Test resolve_from_jwt with complete JWT payload."""
        resolver = IdentityResolver()

        jwt_payload = {
            "sub": "user123",
            "email": "test@example.com",
            "name": "Test User",
            "permissions": ["admin", "read"],
            "iss": "https://example.com",
        }

        user = resolver.resolve_from_jwt(jwt_payload)

        assert isinstance(user, User)
        assert user.user_id == "user123"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.source == IdentitySource.API_JWT
        assert user.platform_id == "user123"
        assert user.permissions == ["admin", "read"]
        assert user.metadata["jwt_iss"] == "https://example.com"

    def test_resolve_from_jwt_with_minimal_claims(self):
        """Test resolve_from_jwt with minimal JWT payload."""
        resolver = IdentityResolver()

        jwt_payload = {
            "sub": "user456",
        }

        user = resolver.resolve_from_jwt(jwt_payload)

        assert user.user_id == "user456"
        assert user.email == "unknown"
        assert user.display_name == "user456"
        assert user.permissions == []

    def test_resolve_from_jwt_missing_sub(self):
        """Test resolve_from_jwt handles missing sub claim."""
        resolver = IdentityResolver()

        jwt_payload = {
            "email": "test@example.com",
        }

        user = resolver.resolve_from_jwt(jwt_payload)

        assert user.user_id == "unknown"
        assert user.platform_id == "unknown"

    def test_resolve_from_jwt_no_permissions(self):
        """Test resolve_from_jwt handles missing permissions."""
        resolver = IdentityResolver()

        jwt_payload = {
            "sub": "user123",
            "email": "test@example.com",
        }

        user = resolver.resolve_from_jwt(jwt_payload)

        assert user.permissions == []

    def test_resolve_from_jwt_display_name_fallback(self):
        """Test resolve_from_jwt falls back to sub for display_name."""
        resolver = IdentityResolver()

        jwt_payload = {
            "sub": "user123",
            "email": "test@example.com",
            # No 'name' field
        }

        user = resolver.resolve_from_jwt(jwt_payload)

        assert user.display_name == "user123"


class TestResolveFromWebhook:
    """Test suite for webhook resolution."""

    def test_resolve_from_webhook_complete_payload(self):
        """Test resolve_from_webhook with complete webhook payload."""
        resolver = IdentityResolver()

        payload = {
            "user_id": "webhook_user",
            "email": "webhook@example.com",
            "name": "Webhook User",
            "client_id": "client123",
            "action": "deploy",
        }

        user = resolver.resolve_from_webhook(payload, webhook_source="github")

        assert isinstance(user, User)
        assert user.user_id == "webhook_user"
        assert user.email == "webhook@example.com"
        assert user.display_name == "Webhook User"
        assert user.source == IdentitySource.WEBHOOK
        assert user.platform_id == "client123"
        assert user.permissions == ["webhook"]
        assert user.metadata["webhook_source"] == "github"

    def test_resolve_from_webhook_defaults(self):
        """Test resolve_from_webhook with minimal payload."""
        resolver = IdentityResolver()

        payload = {}

        user = resolver.resolve_from_webhook(payload)

        assert user.user_id == "system"
        assert user.email == "system@sre-bot.local"
        assert user.display_name == "system"
        assert user.platform_id == "unknown"
        assert user.source == IdentitySource.WEBHOOK

    def test_resolve_from_webhook_default_source(self):
        """Test resolve_from_webhook uses default webhook source."""
        resolver = IdentityResolver()

        payload = {"user_id": "test"}

        user = resolver.resolve_from_webhook(payload)

        assert user.metadata["webhook_source"] == "unknown"

    def test_resolve_from_webhook_custom_source(self):
        """Test resolve_from_webhook respects custom webhook source."""
        resolver = IdentityResolver()

        payload = {"user_id": "test"}

        user = resolver.resolve_from_webhook(payload, webhook_source="gitlab")

        assert user.metadata["webhook_source"] == "gitlab"


class TestResolveSystemIdentity:
    """Test suite for system identity resolution."""

    def test_resolve_system_identity(self):
        """Test resolve_system_identity creates system user."""
        resolver = IdentityResolver()

        user = resolver.resolve_system_identity()

        assert isinstance(user, User)
        assert user.user_id == "system"
        assert user.email == "system@sre-bot.local"
        assert user.display_name == "SRE Bot System"
        assert user.source == IdentitySource.SYSTEM
        assert user.platform_id == "system"
        assert "system" in user.permissions
        assert user.metadata["system"] is True


class TestResolveFromSlack:
    """Test suite for Slack resolution."""

    def test_resolve_from_slack_success(self):
        """Test resolve_from_slack with valid Slack response."""
        mock_client = Mock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {
                "id": "U123ABC",
                "name": "testuser",
                "profile": {
                    "email": "test@example.com",
                    "display_name": "Test User",
                    "real_name": "Test User",
                },
            },
            "team_id": "T456DEF",
        }

        mock_slack_manager = Mock()
        mock_slack_manager.get_client.return_value = mock_client

        resolver = IdentityResolver(slack_client_manager=mock_slack_manager)
        user = resolver.resolve_from_slack("U123ABC")

        assert isinstance(user, SlackUser)
        assert user.user_id == "test@example.com"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.source == IdentitySource.SLACK
        assert user.platform_id == "U123ABC"
        assert user.slack_user_id == "U123ABC"
        assert user.slack_team_id == "T456DEF"
        assert user.slack_user_name == "testuser"

    def test_resolve_from_slack_no_client_manager(self):
        """Test resolve_from_slack raises error without client manager."""
        resolver = IdentityResolver()  # No Slack client

        with pytest.raises(ValueError, match="Slack client manager not configured"):
            resolver.resolve_from_slack("U123ABC")

    def test_resolve_from_slack_api_error(self):
        """Test resolve_from_slack handles API errors."""
        mock_client = Mock()
        mock_client.users_info.return_value = {
            "ok": False,
            "error": "user_not_found",
        }

        mock_slack_manager = Mock()
        mock_slack_manager.get_client.return_value = mock_client

        resolver = IdentityResolver(slack_client_manager=mock_slack_manager)

        with pytest.raises(ValueError, match="Failed to fetch Slack user info"):
            resolver.resolve_from_slack("INVALID")

    def test_resolve_from_slack_missing_profile(self):
        """Test resolve_from_slack handles missing profile."""
        mock_client = Mock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {
                "id": "U123ABC",
                "name": "testuser",
                "profile": {},  # Empty profile
            },
            "team_id": "T456DEF",
        }

        mock_slack_manager = Mock()
        mock_slack_manager.get_client.return_value = mock_client

        resolver = IdentityResolver(slack_client_manager=mock_slack_manager)
        user = resolver.resolve_from_slack("U123ABC")

        assert user.email == ""
        assert user.display_name == ""

    def test_resolve_from_slack_exception_handling(self):
        """Test resolve_from_slack handles exceptions gracefully."""
        mock_client = Mock()
        mock_client.users_info.side_effect = RuntimeError("Network error")

        mock_slack_manager = Mock()
        mock_slack_manager.get_client.return_value = mock_client

        resolver = IdentityResolver(slack_client_manager=mock_slack_manager)

        with pytest.raises(RuntimeError, match="Network error"):
            resolver.resolve_from_slack("U123ABC")
