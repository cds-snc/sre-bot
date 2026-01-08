"""Tests for infrastructure.identity.service module."""

from unittest.mock import Mock

from infrastructure.identity import IdentityService, IdentitySource


class TestIdentityServiceInit:
    """Tests for IdentityService initialization."""

    def test_init_with_resolver(self, mock_settings):
        """IdentityService accepts pre-configured resolver."""
        mock_resolver = Mock()
        service = IdentityService(settings=mock_settings, resolver=mock_resolver)

        assert service.resolver is mock_resolver

    def test_init_without_resolver(self, mock_settings, mock_slack_client_manager):
        """IdentityService creates resolver when not provided."""
        service = IdentityService(
            settings=mock_settings, slack_client_manager=mock_slack_client_manager
        )

        assert service.resolver is not None

    def test_init_creates_resolver_with_default_slack_client(self, mock_settings):
        """IdentityService creates resolver with SlackClientManager when not provided."""
        # This tests that the service can initialize without any optional params
        service = IdentityService(settings=mock_settings)

        assert service.resolver is not None


class TestIdentityServiceResolveFromSlack:
    """Tests for resolve_from_slack method."""

    def test_resolve_from_slack_delegates_to_resolver(
        self, identity_service, make_slack_user
    ):
        """Service delegates to underlying resolver."""
        expected_user = make_slack_user()
        identity_service._resolver.resolve_from_slack = Mock(return_value=expected_user)

        result = identity_service.resolve_from_slack("U123ABC")

        assert result == expected_user
        identity_service._resolver.resolve_from_slack.assert_called_once_with(
            "U123ABC", None
        )

    def test_resolve_from_slack_with_team_id(self, identity_service, make_slack_user):
        """Service passes team_id to resolver."""
        expected_user = make_slack_user()
        identity_service._resolver.resolve_from_slack = Mock(return_value=expected_user)

        result = identity_service.resolve_from_slack("U123ABC", slack_team_id="T456DEF")

        assert result == expected_user
        identity_service._resolver.resolve_from_slack.assert_called_once_with(
            "U123ABC", "T456DEF"
        )


class TestIdentityServiceResolveFromJWT:
    """Tests for resolve_from_jwt method."""

    def test_resolve_from_jwt_delegates_to_resolver(self, identity_service, make_user):
        """Service delegates JWT resolution to resolver."""
        jwt_payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "name": "Test User",
        }
        expected_user = make_user(source=IdentitySource.API_JWT)
        identity_service._resolver.resolve_from_jwt = Mock(return_value=expected_user)

        result = identity_service.resolve_from_jwt(jwt_payload)

        assert result == expected_user
        identity_service._resolver.resolve_from_jwt.assert_called_once_with(jwt_payload)


class TestIdentityServiceResolveFromWebhook:
    """Tests for resolve_from_webhook method."""

    def test_resolve_from_webhook_delegates_to_resolver(
        self, identity_service, make_user
    ):
        """Service delegates webhook resolution to resolver."""
        webhook_payload = {"user_id": "webhook_user", "client_id": "webhook_client"}
        expected_user = make_user(source=IdentitySource.WEBHOOK)
        identity_service._resolver.resolve_from_webhook = Mock(
            return_value=expected_user
        )

        result = identity_service.resolve_from_webhook(webhook_payload)

        assert result == expected_user
        identity_service._resolver.resolve_from_webhook.assert_called_once_with(
            webhook_payload, "unknown"
        )

    def test_resolve_from_webhook_with_source(self, identity_service, make_user):
        """Service passes webhook source to resolver."""
        webhook_payload = {"user_id": "webhook_user"}
        expected_user = make_user(source=IdentitySource.WEBHOOK)
        identity_service._resolver.resolve_from_webhook = Mock(
            return_value=expected_user
        )

        result = identity_service.resolve_from_webhook(
            webhook_payload, webhook_source="github"
        )

        assert result == expected_user
        identity_service._resolver.resolve_from_webhook.assert_called_once_with(
            webhook_payload, "github"
        )


class TestIdentityServiceResolveSystemIdentity:
    """Tests for resolve_system_identity method."""

    def test_resolve_system_identity_delegates_to_resolver(
        self, identity_service, make_user
    ):
        """Service delegates system identity resolution to resolver."""
        expected_user = make_user(
            user_id="system",
            email="system@sre-bot.local",
            display_name="SRE Bot System",
            source=IdentitySource.SYSTEM,
        )
        identity_service._resolver.resolve_system_identity = Mock(
            return_value=expected_user
        )

        result = identity_service.resolve_system_identity()

        assert result == expected_user
        identity_service._resolver.resolve_system_identity.assert_called_once()


class TestIdentityServiceResolverProperty:
    """Tests for resolver property."""

    def test_resolver_property_returns_underlying_resolver(
        self, identity_service, mock_slack_client_manager
    ):
        """Resolver property provides access to underlying resolver."""
        assert identity_service.resolver is identity_service._resolver
