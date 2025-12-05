"""Fixtures for infrastructure event system tests."""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock

from infrastructure.events.models import Event
from infrastructure.events.dispatcher import clear_handlers


@pytest.fixture
def event_factory():
    """Factory for creating test events."""

    def _factory(
        event_type: str = "test.event",
        timestamp: datetime = None,
        correlation_id=None,
        user_email: str = "test@example.com",
        metadata: dict = None,
    ):
        return Event(
            event_type=event_type,
            timestamp=timestamp or datetime.now(),
            correlation_id=correlation_id or uuid4(),
            user_email=user_email,
            metadata=metadata or {},
        )

    return _factory


@pytest.fixture
def clear_event_handlers():
    """Clear event handlers before and after test."""
    clear_handlers()
    yield
    clear_handlers()


@pytest.fixture
def mock_event_handler():
    """Mock event handler function."""
    return MagicMock()


@pytest.fixture
def mock_sentinel_client():
    """Mock Sentinel client for audit handler testing."""
    mock = MagicMock()
    mock.log_to_sentinel = MagicMock(return_value={"success": True})
    return mock


@pytest.fixture
def discovery_fixture_path(tmp_path):
    """Create a temporary module structure for discovery testing.

    Returns a Path to a temporary modules directory with test handlers.
    """
    # Create temporary module structure
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    # Create __init__.py
    (modules_dir / "__init__.py").write_text("")

    # Create a test feature module
    test_module_dir = modules_dir / "test_feature"
    test_module_dir.mkdir()
    (test_module_dir / "__init__.py").write_text("")

    # Create events.handlers module
    events_dir = test_module_dir / "events"
    events_dir.mkdir()
    (events_dir / "__init__.py").write_text("")

    handlers_file = events_dir / "handlers.py"
    handlers_file.write_text(
        '''
from infrastructure.events import register_event_handler, Event

@register_event_handler("test.event")
def handle_test_event(event: Event) -> None:
    """Test event handler."""
    pass
'''
    )

    return modules_dir
