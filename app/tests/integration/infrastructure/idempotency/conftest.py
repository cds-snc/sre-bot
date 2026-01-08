"""Fixtures for idempotency integration tests."""

import pytest


@pytest.fixture
def mock_settings(make_mock_settings):
    """Create mock settings for idempotency integration tests.

    Uses the factory from root conftest to avoid duplication
    across different test packages.
    """
    return make_mock_settings(
        **{
            "idempotency.IDEMPOTENCY_TTL_SECONDS": 3600,
        }
    )
