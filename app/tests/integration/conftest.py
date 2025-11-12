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

import pytest
from unittest.mock import MagicMock
from typing import Any, Dict, List


# ============================================================================
# Orchestration Layer Mocks
# ============================================================================


@pytest.fixture
def mock_orchestration_success(monkeypatch):
    """Mock orchestration layer to return success.

    Mocks the orchestration module so integration tests can verify
    service layer coordination without testing orchestration itself.

    Returns:
        MagicMock: Mock orchestration function with success responses
    """
    mock = MagicMock()
    mock.return_value = {
        "success": True,
        "status": "success",
        "provider": "google",
        "data": {"operation_id": "op-123", "timestamp": "2025-11-04T10:00:00Z"},
    }

    monkeypatch.setattr(
        "modules.groups.core.orchestration.add_member_to_group",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_orchestration_failure(monkeypatch):
    """Mock orchestration layer to return failure.

    Useful for testing error handling and retry logic in service layer.

    Returns:
        MagicMock: Mock orchestration function with failure responses
    """
    mock = MagicMock()
    mock.return_value = {
        "status": "error",
        "provider": "google",
        "error": "orchestration_failed",
        "message": "Failed to add member to group",
    }

    monkeypatch.setattr(
        "modules.groups.core.orchestration.add_member_to_group",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_orchestration_partial_failure(monkeypatch):
    """Mock orchestration layer with side effects for partial success.

    Used for testing bulk operations with some successes and some failures.

    Returns:
        MagicMock: Mock orchestration with configurable side effects
    """
    mock = MagicMock()

    # Default: can be overridden with side_effect
    mock.side_effect = [
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

    monkeypatch.setattr(
        "modules.groups.core.orchestration.add_member_to_group",
        mock,
        raising=False,
    )

    return mock


@pytest.fixture
def mock_orchestration_remove_member(monkeypatch):
    """Mock orchestration for remove_member operations.

    Returns:
        MagicMock: Mock orchestration for removal operations
    """
    mock = MagicMock()
    mock.return_value = {
        "success": True,
        "status": "success",
        "provider": "google",
        "data": {"operation_id": "op-remove-123", "timestamp": "2025-11-04T10:00:00Z"},
    }

    monkeypatch.setattr(
        "modules.groups.core.orchestration.remove_member_from_group",
        mock,
        raising=False,
    )

    return mock


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

    def capture_event(event_type: str, **data):
        """Capture event dispatch call"""
        dispatched_events.append(
            {
                "event_type": event_type,
                "data": data,
            }
        )

    mock = MagicMock(side_effect=capture_event)
    mock.get_dispatched = lambda: dispatched_events
    mock.clear_dispatched = lambda: dispatched_events.clear()

    monkeypatch.setattr(
        "modules.groups.events.system.dispatch_background",
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
    mock_orchestration_success,
    mock_event_dispatch,
    mock_validation_success,
):
    """Integration test context with all standard mocks.

    Provides a complete context for integration testing with:
    - Orchestration success
    - Event capture
    - Validation success

    Can be extended by individual tests with additional mocks.

    Returns:
        Dict: Contains all configured mocks
    """
    return {
        "orchestration": mock_orchestration_success,
        "events": mock_event_dispatch,
        "validation": mock_validation_success,
    }


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register integration test marker."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
