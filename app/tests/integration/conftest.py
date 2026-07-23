"""Root-level conftest.py for integration tests.

Provides shared integration fixtures for external system boundary isolation and
application lifespan initialization.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from server.server import handler


@pytest.fixture(autouse=True)
def _autouse_mock_dynamodb_audit(monkeypatch):
    """Automatically mock DynamoDB audit writes for all integration tests.

    Integration tests should not write to actual DynamoDB tables.
    This autouse fixture mocks the audit persistence layer to prevent
    actual database writes during testing.
    """
    mock = MagicMock()
    monkeypatch.setattr(
        "infrastructure.audit.service.DynamoDBAuditTrailService.write_audit_event",
        mock,
        raising=False,
    )
    return mock


@pytest.fixture(autouse=True)
def _autouse_mock_sentinel_client(monkeypatch):
    """Automatically mock Sentinel client for all integration tests.

    Integration tests should not make real calls to external systems.
    This autouse fixture mocks the Sentinel client at the system boundary
    at all import locations to prevent actual Sentinel calls.

    Note: Individual tests can override or assert on the mock behavior
    by requesting the mock_sentinel_client fixture.
    """
    mock = MagicMock()
    mock.return_value = True

    # Patch at all possible import locations
    monkeypatch.setattr(
        "integrations.sentinel.client.log_to_sentinel",
        mock,
        raising=False,
    )
    monkeypatch.setattr(
        "integrations.sentinel.client.log_audit_event",
        mock,
        raising=False,
    )
    # Patch where sentinel is called from the audit service
    monkeypatch.setattr(
        "integrations.sentinel.client.log_audit_event",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_sentinel_client(monkeypatch):
    """Mock Sentinel client to prevent actual external calls.

    Integration tests should not make real calls to external systems.
    This fixture mocks the Sentinel client at the system boundary.

    Note: For most integration tests, the autouse fixture
    _autouse_mock_sentinel_client is automatically applied.

    Returns:
        MagicMock: Mock Sentinel client
    """
    mock = MagicMock()
    mock.return_value = True

    monkeypatch.setattr(
        "integrations.sentinel.client.log_to_sentinel",
        mock,
        raising=False,
    )

    return mock


# ============================================================================
# Settings Mocks
# ============================================================================


@pytest.fixture
def mock_settings(make_mock_settings):
    """Create base mock settings for integration tests.

    This fixture provides default settings for all integration tests.
    Child conftest files can override this to provide package-specific settings.

    Uses the factory from root conftest to avoid duplication.
    """
    return make_mock_settings(
        **{
            "idempotency.IDEMPOTENCY_TTL_SECONDS": 3600,
        }
    )


# ============================================================================
# FastAPI App Fixtures
# ============================================================================


@pytest.fixture
def app_with_lifespan(monkeypatch):
    """Provide a real FastAPI app instance with lifespan context.

    This fixture exercises the full app initialization lifecycle including:
    - Lifespan startup (settings, logger, providers, bot initialization)
    - Request/response cycle
    - Lifespan shutdown

    Use this for end-to-end integration tests that need to validate:
    - app.state is properly initialized
    - HTTP routes work with real app context
    - Graceful error handling when dependencies are unavailable

    Returns:
        TestClient: FastAPI TestClient with real app initialized
    """
    mock_directory_provider = MagicMock()
    mock_directory_provider.warmup.return_value = MagicMock(
        is_success=True,
        message="ok",
    )

    monkeypatch.setattr(
        "server.lifespan.get_directory_provider",
        lambda: mock_directory_provider,
    )

    # Create client which triggers lifespan context manager
    with TestClient(handler) as client:
        yield client


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register integration test marker."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
