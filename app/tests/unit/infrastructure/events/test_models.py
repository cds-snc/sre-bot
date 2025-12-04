"""Unit tests for infrastructure event models."""

import pytest
from datetime import datetime
from uuid import uuid4

from infrastructure.events.models import Event

pytestmark = pytest.mark.unit


class TestEvent:
    """Tests for Event base class."""

    def test_event_creation_with_all_fields(self, event_factory):
        """Test creating event with all required fields."""
        event = event_factory(
            event_type="test.action",
            user_email="user@example.com",
            metadata={"key": "value"},
        )

        assert event.event_type == "test.action"
        assert event.user_email == "user@example.com"
        assert event.metadata == {"key": "value"}
        assert isinstance(event.timestamp, datetime)
        assert event.correlation_id is not None

    def test_event_creation_with_defaults(self):
        """Test creating event with default values."""
        event = Event(event_type="test.event")

        assert event.event_type == "test.event"
        assert event.user_email == ""
        assert event.metadata == {}
        assert isinstance(event.timestamp, datetime)
        assert event.correlation_id is not None

    def test_event_to_dict_serialization(self, event_factory):
        """Test event serialization to dict."""
        event = event_factory()
        event_dict = event.to_dict()

        assert "event_type" in event_dict
        assert "timestamp" in event_dict
        assert "correlation_id" in event_dict
        assert "user_email" in event_dict
        assert "metadata" in event_dict
        assert isinstance(event_dict["timestamp"], str)
        assert isinstance(event_dict["correlation_id"], str)

    def test_event_from_dict_deserialization(self, event_factory):
        """Test event deserialization from dict."""
        original_event = event_factory(
            event_type="test.event",
            user_email="user@example.com",
            metadata={"key": "value"},
        )
        event_dict = original_event.to_dict()

        restored_event = Event.from_dict(event_dict)

        assert restored_event.event_type == original_event.event_type
        assert restored_event.user_email == original_event.user_email
        assert restored_event.metadata == original_event.metadata
        assert str(restored_event.correlation_id) == event_dict["correlation_id"]

    def test_event_from_dict_with_string_timestamp(self):
        """Test deserializing event with string timestamp."""
        data = {
            "event_type": "test.event",
            "timestamp": "2025-12-04T10:30:00",
            "correlation_id": str(uuid4()),
            "user_email": "user@example.com",
            "metadata": {},
        }

        event = Event.from_dict(data)

        assert event.event_type == "test.event"
        assert isinstance(event.timestamp, datetime)

    def test_event_from_dict_missing_required_field(self):
        """Test deserializing event with missing required field."""
        data = {"timestamp": datetime.now(), "user_email": "user@example.com"}

        with pytest.raises(ValueError):
            Event.from_dict(data)

    def test_event_hash(self, event_factory):
        """Test event hashing based on correlation_id and timestamp."""
        event1 = event_factory()
        event2 = Event(
            event_type="different",
            correlation_id=event1.correlation_id,
            timestamp=event1.timestamp,
        )

        assert hash(event1) == hash(event2)

    def test_event_different_hash(self, event_factory):
        """Test different events have different hashes."""
        event1 = event_factory()
        event2 = event_factory()

        assert hash(event1) != hash(event2)
