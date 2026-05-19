"""Tests for PR-6: provider narrow-slice migration.

Verifies each provider calls only its domain singleton
instead of the full Settings aggregator.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.clients.maxmind.client import MaxMindClient
from infrastructure.configuration.infrastructure.platforms import PlatformsSettings
from infrastructure.configuration.infrastructure.retry import RetrySettings
from infrastructure.configuration.integrations.maxmind import MaxMindSettings
from infrastructure.configuration.integrations.slack import SlackSettings
from infrastructure.platforms.clients.slack import get_slack_client
from infrastructure.platforms.service import PlatformService, get_platform_service
from infrastructure.resilience.service import ResilienceService
from infrastructure.services.providers import (
    get_maxmind_client,
)

pytestmark = pytest.mark.unit


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

    def test_get_platform_service_uses_platforms_settings(self):
        """get_platform_service uses get_platforms_settings, not get_settings."""
        get_platform_service.cache_clear()
        with (
            patch(
                "infrastructure.configuration.settings.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.platforms.service.get_platforms_settings"
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

    def test_get_slack_client_uses_slack_settings(self):
        """get_slack_client uses get_slack_settings, not get_settings."""
        get_slack_client.cache_clear()
        with (
            patch(
                "infrastructure.configuration.settings.get_settings"
            ) as mock_get_settings,
            patch(
                "infrastructure.platforms.clients.slack.get_slack_settings"
            ) as mock_slack,
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
