"""Tests for provider narrow-slice construction.

Verifies each provider calls only its domain singleton
instead of the full Settings aggregator.
"""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from integrations.maxmind.client import MaxMindClient

pytestmark = pytest.mark.unit


class TestMaxMindClientNarrowSlice:
    """MaxMindClient takes only its database path, never a settings object."""

    def test_accepts_the_database_path(self):
        """MaxMindClient constructs with the [maxmind.tenant] database path."""
        with tempfile.NamedTemporaryFile(suffix=".mmdb", delete=False) as f:
            db_path = f.name
        try:
            client = MaxMindClient(database_path=db_path)
            assert client._db_path == db_path
        finally:
            os.unlink(db_path)

    def test_rejects_full_settings_positional(self):
        """MaxMindClient does not accept generic 'settings' kwarg."""
        mock_settings = MagicMock()
        with pytest.raises(TypeError):
            MaxMindClient(settings=mock_settings)
