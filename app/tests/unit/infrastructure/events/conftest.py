"""Fixtures for infrastructure event system tests."""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from infrastructure.events import get_event_dispatcher
from infrastructure.events.models import Event
from infrastructure.events.service import EventDispatcher


@pytest.fixture(autouse=True)
def clear_event_dispatcher_cache() -> None:
    """Clear cached dispatcher singleton between tests for isolation."""
    get_event_dispatcher.cache_clear()
    yield
    get_event_dispatcher.cache_clear()


@pytest.fixture
def event_factory():
    """Factory for creating test events."""

    def _factory(
        event_type: str = "test.event",
        timestamp: datetime | None = None,
        correlation_id=None,
        user_email: str = "test@example.com",
        metadata: dict | None = None,
    ) -> Event[dict]:
        return Event(
            event_type=event_type,
            timestamp=timestamp or datetime.now(),
            correlation_id=correlation_id or uuid4(),
            user_email=user_email,
            metadata=metadata or {},
        )

    return _factory


@pytest.fixture
def dispatcher() -> EventDispatcher:
    """Fresh EventDispatcher instance for each test."""
    event_dispatcher = EventDispatcher()
    yield event_dispatcher
    event_dispatcher.shutdown_executor(wait=False)


@pytest.fixture
def mock_handler() -> MagicMock:
    """Mock event handler with a stable function name for logging assertions."""
    handler = MagicMock()
    handler.__name__ = "mock_handler"
    return handler
