"""Fixtures for idempotency integration tests."""

from unittest.mock import MagicMock

import pytest

from infrastructure.configuration.infrastructure.idempotency import IdempotencySettings


@pytest.fixture
def mock_settings():
    """Create mock IdempotencySettings for idempotency integration tests."""
    mock = MagicMock(spec=IdempotencySettings)
    mock.IDEMPOTENCY_TTL_SECONDS = 3600
    return mock
