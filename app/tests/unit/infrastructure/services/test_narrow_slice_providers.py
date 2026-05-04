"""Tests for PR-6: provider narrow-slice migration.

Verifies each provider calls only its domain singleton
instead of the full Settings aggregator.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from infrastructure.configuration.infrastructure.server import ServerSettings
from infrastructure.configuration.infrastructure.idempotency import IdempotencySettings
from infrastructure.configuration.infrastructure.retry import RetrySettings
from infrastructure.configuration.infrastructure.platforms import PlatformsSettings
from infrastructure.configuration.integrations.maxmind import MaxMindSettings
from infrastructure.configuration.integrations.slack import SlackSettings
from infrastructure.configuration.features.commands import CommandsSettings
from infrastructure.identity.service import IdentityService
from infrastructure.clients.maxmind.client import MaxMindClient
from infrastructure.idempotency.service import IdempotencyService
from infrastructure.resilience.service import ResilienceService
from infrastructure.notifications.service import NotificationService
from infrastructure.commands.service import CommandService
from infrastructure.platforms.service import PlatformService
from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.services.providers import (
    get_command_service,
    get_identity_service,
    get_idempotency_service,
    get_jwks_manager,
    get_maxmind_client,
    get_platform_service,
    get_resilience_service,
    get_slack_client,
)

pytestmark = pytest.mark.unit


class TestIdentityServiceNarrowSlice:
    """IdentityService accepts server_settings instead of full Settings."""

    def test_accepts_server_settings_kwarg(self):
        """IdentityService constructs with server_settings parameter."""
        mock_server_settings = MagicMock(spec=ServerSettings)
        resolver = MagicMock()
        service = IdentityService(
            server_settings=mock_server_settings, resolver=resolver
        )
        assert service is not None

    def test_constructs_without_settings(self):
        """IdentityService can construct with no settings (settings unused)."""
        resolver = MagicMock()
        service = IdentityService(resolver=resolver)
        assert service is not None


class TestMaxMindClientNarrowSlice:
    """MaxMindClient accepts maxmind_settings instead of full Settings."""

    def test_accepts_maxmind_settings(self):
        """MaxMindClient constructs with maxmind_settings parameter."""
        mock_settings = MagicMock(spec=MaxMindSettings)
        with tempfile.NamedTemporaryFile(suffix=".mmdb", delete=False) as f:
            db_path = f.name
        try:
            mock_settings.MAXMIND_DB_PATH = db_path
            client = MaxMindClient(maxmind_settings=mock_settings)
            assert client._db_path == db_path
        finally:
            os.unlink(db_path)

    def test_rejects_full_settings_positional(self):
        """MaxMindClient does not accept generic 'settings' kwarg."""
        mock_settings = MagicMock()
        with pytest.raises(TypeError):
            MaxMindClient(settings=mock_settings)


class TestIdempotencyServiceNarrowSlice:
    """IdempotencyService accepts idempotency_settings instead of full Settings."""

    def test_accepts_idempotency_settings_with_cache(self):
        """IdempotencyService constructs with idempotency_settings + injected cache."""
        mock_settings = MagicMock(spec=IdempotencySettings)
        mock_cache = MagicMock()
        service = IdempotencyService(
            idempotency_settings=mock_settings, cache=mock_cache
        )
        assert service is not None

    def test_rejects_full_settings_kwarg(self):
        """IdempotencyService does not accept 'settings' kwarg."""
        mock_settings = MagicMock()
        mock_cache = MagicMock()
        with pytest.raises(TypeError):
            IdempotencyService(settings=mock_settings, cache=mock_cache)


class TestResilienceServiceNarrowSlice:
    """ResilienceService accepts retry_settings instead of full Settings."""

    def test_accepts_retry_settings_with_store(self):
        """ResilienceService constructs with retry_settings + injected store."""
        mock_settings = MagicMock(spec=RetrySettings)
        mock_store = MagicMock()
        service = ResilienceService(
            retry_settings=mock_settings, retry_store=mock_store
        )
        assert service is not None

    def test_rejects_full_settings_kwarg(self):
        """ResilienceService does not accept 'settings' kwarg."""
        mock_settings = MagicMock()
        mock_store = MagicMock()
        with pytest.raises(TypeError):
            ResilienceService(settings=mock_settings, retry_store=mock_store)


class TestNotificationServiceNarrowSlice:
    """NotificationService accepts pre-built channels instead of full Settings."""

    def test_accepts_channels_with_dispatcher(self):
        """NotificationService constructs with pre-built channels + injected dispatcher."""
        mock_channel = MagicMock(spec=ChatChannel)
        mock_dispatcher = MagicMock()
        service = NotificationService(
            channels={"chat": mock_channel},
            dispatcher=mock_dispatcher,
        )
        assert service is not None

    def test_rejects_full_settings_kwarg(self):
        """NotificationService does not accept 'settings' kwarg."""
        mock_settings = MagicMock()
        mock_dispatcher = MagicMock()
        with pytest.raises(TypeError):
            NotificationService(settings=mock_settings, dispatcher=mock_dispatcher)


class TestCommandServiceNarrowSlice:
    """CommandService accepts commands_settings instead of full Settings."""

    def test_accepts_commands_settings(self):
        """CommandService constructs with commands_settings parameter."""
        mock_settings = MagicMock(spec=CommandsSettings)
        service = CommandService(commands_settings=mock_settings)
        assert service is not None

    def test_constructs_without_settings(self):
        """CommandService can construct with no settings (settings unused)."""
        service = CommandService()
        assert service is not None

    def test_rejects_full_settings_kwarg(self):
        """CommandService does not accept 'settings' kwarg."""
        mock_settings = MagicMock()
        with pytest.raises(TypeError):
            CommandService(settings=mock_settings)


class TestPlatformServiceNarrowSlice:
    """PlatformService accepts platforms_settings instead of full Settings."""

    def test_accepts_platforms_settings(self):
        """PlatformService constructs with platforms_settings parameter."""
        mock_settings = MagicMock(spec=PlatformsSettings)
        mock_settings.slack = MagicMock()
        mock_settings.slack.ENABLED = False
        service = PlatformService(platforms_settings=mock_settings)
        assert service is not None

    def test_rejects_full_settings_kwarg(self):
        """PlatformService does not accept 'settings' kwarg."""
        mock_settings = MagicMock()
        with pytest.raises(TypeError):
            PlatformService(settings=mock_settings)


class TestProvidersDontCallGetSettings:
    """Providers in providers.py use domain singletons, not get_settings()."""

    def test_get_identity_service_calls_server_settings_not_get_settings(self):
        """get_identity_service uses get_server_settings, not get_settings."""
        get_identity_service.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.configuration.infrastructure.server.get_server_settings"
            ),
        ):
            get_identity_service()
            mock_get_settings.assert_not_called()
        get_identity_service.cache_clear()

    def test_get_maxmind_client_uses_maxmind_settings(self):
        """get_maxmind_client uses get_maxmind_settings, not get_settings."""
        get_maxmind_client.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.services.providers.get_maxmind_settings"
            ) as mock_maxmind,
            patch(
                "infrastructure.clients.maxmind.client.MaxMindClient.__init__",
                return_value=None,
            ),
        ):
            mock_maxmind.return_value = MagicMock(spec=MaxMindSettings)
            get_maxmind_client()
            mock_get_settings.assert_not_called()
            mock_maxmind.assert_called_once()
        get_maxmind_client.cache_clear()

    def test_get_idempotency_service_uses_idempotency_settings(self):
        """get_idempotency_service uses get_idempotency_settings, not get_settings."""
        get_idempotency_service.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.services.providers.get_idempotency_settings"
            ) as mock_idempotency,
        ):
            mock_idempotency.return_value = MagicMock(spec=IdempotencySettings)
            with patch(
                "infrastructure.idempotency.service.IdempotencyService.__init__",
                return_value=None,
            ):
                get_idempotency_service()
            mock_get_settings.assert_not_called()
            mock_idempotency.assert_called_once()
        get_idempotency_service.cache_clear()

    def test_get_resilience_service_uses_retry_settings(self):
        """get_resilience_service uses get_retry_settings, not get_settings."""
        get_resilience_service.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch("infrastructure.services.providers.get_retry_settings") as mock_retry,
        ):
            mock_retry.return_value = MagicMock(spec=RetrySettings)
            with patch(
                "infrastructure.resilience.service.ResilienceService.__init__",
                return_value=None,
            ):
                get_resilience_service()
            mock_get_settings.assert_not_called()
            mock_retry.assert_called_once()
        get_resilience_service.cache_clear()

    def test_get_command_service_uses_commands_settings(self):
        """get_command_service uses get_commands_settings, not get_settings."""
        get_command_service.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.services.providers.get_commands_settings"
            ) as mock_commands,
        ):
            mock_commands.return_value = MagicMock(spec=CommandsSettings)
            get_command_service()
            mock_get_settings.assert_not_called()
            mock_commands.assert_called_once()
        get_command_service.cache_clear()

    def test_get_platform_service_uses_platforms_settings(self):
        """get_platform_service uses get_platforms_settings, not get_settings."""
        get_platform_service.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.services.providers.get_platforms_settings"
            ) as mock_platforms,
        ):
            mock_platforms.return_value = MagicMock(spec=PlatformsSettings)
            with patch(
                "infrastructure.platforms.service.PlatformService.__init__",
                return_value=None,
            ):
                get_platform_service()
            mock_get_settings.assert_not_called()
            mock_platforms.assert_called_once()
        get_platform_service.cache_clear()

    def test_get_jwks_manager_uses_server_settings(self):
        """get_jwks_manager uses get_server_settings, not get_settings."""
        get_jwks_manager.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.services.providers.get_server_settings"
            ) as mock_server,
        ):
            mock_server.return_value = MagicMock(spec=ServerSettings)
            mock_server.return_value.ISSUER_CONFIG = {"issuer": "https://test.example"}
            with patch(
                "infrastructure.security.jwks.JWKSManager.__init__", return_value=None
            ):
                get_jwks_manager()
            mock_get_settings.assert_not_called()
            mock_server.assert_called_once()
        get_jwks_manager.cache_clear()

    def test_get_slack_client_uses_slack_settings(self):
        """get_slack_client uses get_slack_settings, not get_settings."""
        get_slack_client.cache_clear()
        with (
            patch(
                "infrastructure.services.providers.get_settings"
            ) as mock_get_settings,
            patch("infrastructure.services.providers.get_slack_settings") as mock_slack,
        ):
            mock_slack.return_value = MagicMock(spec=SlackSettings)
            mock_slack.return_value.SLACK_TOKEN = "xoxb-test"
            with patch(
                "infrastructure.platforms.clients.slack.SlackClientFacade.__init__",
                return_value=None,
            ):
                get_slack_client()
            mock_get_settings.assert_not_called()
            mock_slack.assert_called_once()
        get_slack_client.cache_clear()
