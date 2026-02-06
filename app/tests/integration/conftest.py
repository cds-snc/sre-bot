"""
Root-level conftest.py for integration tests.

Provides system boundary mocks for integration testing:
- Orchestration layer mocking
- Event dispatch capture
- Validation layer failure scenarios
- System boundary configuration

Integration tests mock at system boundaries to test component interaction
without testing the mocked components themselves.
"""

import types
import pytest
from unittest.mock import MagicMock
from typing import Any, Dict, List


# ============================================================================
# Orchestration Layer Mocks
# ============================================================================


@pytest.fixture
def mock_orchestration(monkeypatch):
    """Configurable mock orchestration layer for integration tests.

    Can be configured for success, failure, or partial failure scenarios.
    Tests can override behavior by setting return_value or side_effect.

    Usage:
        def test_something(mock_orchestration):
            mock_orchestration.return_value = {"status": "success"}

    Returns:
        MagicMock: Configurable mock orchestration function
    """
    # Default: success response
    add_mock = MagicMock()
    add_mock.return_value = {
        "success": True,
        "status": "success",
        "provider": "google",
        "data": {"operation_id": "op-123", "timestamp": "2025-11-04T10:00:00Z"},
    }

    # Remove member mock
    remove_mock = MagicMock()
    remove_mock.return_value = {
        "success": True,
        "status": "success",
        "provider": "google",
        "data": {"operation_id": "op-remove-123", "timestamp": "2025-11-04T10:00:00Z"},
    }

    monkeypatch.setattr(
        "modules.groups.core.orchestration.add_member_to_group",
        add_mock,
        raising=False,
    )
    monkeypatch.setattr(
        "modules.groups.core.orchestration.remove_member_from_group",
        remove_mock,
        raising=False,
    )

    # Return both mocks as a namespace for easy access
    return types.SimpleNamespace(
        add_member=add_mock,
        remove_member=remove_mock,
    )


# ============================================================================
# Event Dispatch Mocks & Capture
# ============================================================================


@pytest.fixture
def mock_event_dispatch(monkeypatch):
    """Mock event dispatch system and capture dispatched events.

    Allows integration tests to verify that events are dispatched with
    correct data without testing the event system itself.

    Returns:
        MagicMock: Mock event dispatch function that captures events
    """
    dispatched_events: List[Dict[str, Any]] = []

    def capture_event(event: Any):
        """Capture event dispatch call"""
        # Extract event data
        event_data = None
        if hasattr(event, "to_dict"):
            event_data = event.to_dict()
        elif hasattr(event, "model_dump"):
            event_data = event.model_dump()
        elif hasattr(event, "__dict__"):
            event_data = event.__dict__
        else:
            event_data = event

        dispatched_events.append(event_data)

    mock = MagicMock(side_effect=capture_event)
    mock.get_dispatched = lambda: dispatched_events
    mock.clear_dispatched = lambda: dispatched_events.clear()

    monkeypatch.setattr(
        "modules.groups.core.service.dispatch_background",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture(autouse=True)
def _autouse_mock_dynamodb_audit(monkeypatch):
    """Automatically mock DynamoDB audit writes for all integration tests.

    Integration tests should not write to actual DynamoDB tables.
    This autouse fixture mocks the audit persistence layer to prevent
    actual database writes during testing.
    """
    mock = MagicMock()
    monkeypatch.setattr(
        "infrastructure.events.handlers.audit.dynamodb_audit.write_audit_event",
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
    # Patch where it's imported in the audit handler
    monkeypatch.setattr(
        "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
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


@pytest.fixture
def mock_event_system(monkeypatch):
    """Mock entire event system for integration tests.

    Provides complete event system mock with both dispatch and subscription
    mocking for testing event-driven workflows.

    Returns:
        Dict: Contains mocked dispatch and subscription functions
    """
    dispatched_events = []
    subscribers = {}

    def dispatch(event_type: str, **data):
        """Capture dispatch"""
        dispatched_events.append({"event_type": event_type, "data": data})

    def subscribe(event_type: str, handler):
        """Track subscription"""
        if event_type not in subscribers:
            subscribers[event_type] = []
        subscribers[event_type].append(handler)

    monkeypatch.setattr(
        "modules.groups.events.dispatch_event",
        dispatch,
        raising=False,
    )

    return {
        "dispatch": MagicMock(side_effect=dispatch),
        "subscribe": MagicMock(side_effect=subscribe),
        "get_dispatched": lambda: dispatched_events,
        "get_subscribers": lambda: subscribers,
        "clear": lambda: (dispatched_events.clear(), subscribers.clear()),
    }


# ============================================================================
# Validation Layer Mocks
# ============================================================================


@pytest.fixture
def mock_validation_success(monkeypatch):
    """Mock validation to always pass.

    Returns:
        MagicMock: Mock validation function that returns success
    """
    mock = MagicMock()
    mock.return_value = {"valid": True, "errors": []}

    monkeypatch.setattr(
        "modules.groups.validation.validate_request",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_validation_failure(monkeypatch):
    """Mock validation to return failure.

    Returns:
        MagicMock: Mock validation function that returns errors
    """
    mock = MagicMock()
    mock.return_value = {
        "valid": False,
        "errors": ["Invalid email format", "Group not found"],
    }

    monkeypatch.setattr(
        "modules.groups.validation.validate_request",
        mock,
        raising=False,
    )

    return mock


# ============================================================================
# System Boundary Configuration
# ============================================================================


@pytest.fixture
def isolated_group_service():
    """Provide group service with all external boundaries mocked.

    This fixture can be used by individual test functions to get a
    pre-configured service instance with all system boundaries isolated.

    Returns:
        module: Mocked group service module
    """
    from modules.groups.core import service

    return service


@pytest.fixture
def integration_test_context(
    mock_orchestration,
    mock_event_dispatch,
    mock_validation_success,
):
    """Integration test context with all standard mocks.

    Provides a complete context for integration testing with:
    - Orchestration success (add_member and remove_member)
    - Event capture
    - Validation success

    Can be extended by individual tests with additional mocks.

    Returns:
        Dict: Contains all configured mocks
    """
    return {
        "orchestration": mock_orchestration.add_member,
        "events": mock_event_dispatch,
        "validation": mock_validation_success,
    }
    return {
        "orchestration": mock_orchestration.add_member,
        "events": mock_event_dispatch,
        "validation": mock_validation_success,
    }


# ============================================================================
# Backward Compatibility: Old Fixture Names -> New Fixture
# ============================================================================
# These fixtures maintain backward compatibility with tests that use
# the old fixture names. They delegate to the new mock_orchestration fixture.


@pytest.fixture
def mock_orchestration_success(mock_orchestration):
    """Backward compatibility: old fixture name for add_member mock."""
    return mock_orchestration.add_member


@pytest.fixture
def mock_orchestration_remove_member(mock_orchestration):
    """Backward compatibility: old fixture name for remove_member mock."""
    return mock_orchestration.remove_member


@pytest.fixture
def mock_orchestration_failure(mock_orchestration):
    """Backward compatibility: old fixture name for failure scenario."""
    failure_response = {
        "status": "error",
        "provider": "google",
        "error": "orchestration_failed",
        "message": "Failed to add member to group",
    }
    mock_orchestration.add_member.return_value = failure_response
    return mock_orchestration.add_member


@pytest.fixture
def mock_orchestration_partial_failure(mock_orchestration):
    """Backward compatibility: old fixture name for partial failure scenario."""
    mock_orchestration.add_member.side_effect = [
        {
            "status": "success",
            "provider": "google",
            "data": {"operation_id": "op-1"},
        },
        {
            "status": "error",
            "provider": "google",
            "error": "member_already_exists",
        },
        {
            "status": "success",
            "provider": "google",
            "data": {"operation_id": "op-3"},
        },
    ]
    return mock_orchestration.add_member


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
            "commands.providers": {},
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
    from fastapi.testclient import TestClient
    from server.server import handler

    # Create client which triggers lifespan context manager
    with TestClient(handler) as client:
        yield client


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register integration test marker."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
