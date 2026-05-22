"""Tests for PR-6: provider narrow-slice migration.

Verifies each provider calls only its domain singleton
instead of the full Settings aggregator.
"""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from infrastructure.clients.maxmind.client import MaxMindClient
from infrastructure.configuration.infrastructure.retry import RetrySettings
from infrastructure.configuration.integrations.maxmind import MaxMindSettings
from infrastructure.resilience.service import ResilienceService

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
