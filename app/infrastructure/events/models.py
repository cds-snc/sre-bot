"""Event models for infrastructure event system.

Provides generic Event base class and protocol for event handlers.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict
from uuid import UUID, uuid4


@dataclass
class Event:
    """Base class for all events in the system.

    Events are immutable records of something that happened, used for
    audit trails, notifications, and cross-module communication.
    """

    event_type: str
    """The type of event (e.g., 'group.member.added')."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the event occurred."""

    correlation_id: UUID = field(default_factory=uuid4)
    """Unique ID to track related events across the system."""

    user_email: str = ""
    """User who triggered the event."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Custom metadata for this event type."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary.

        Returns:
            Dictionary representation of the event with ISO format timestamp
            and UUID as string.
        """
        data = asdict(self)
        # Convert datetime to ISO format string
        data["timestamp"] = self.timestamp.isoformat()
        # Convert UUID to string
        data["correlation_id"] = str(self.correlation_id)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserialize event from dictionary.

        Args:
            data: Dictionary with event fields.

        Returns:
            Event instance.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        try:
            # Convert ISO format timestamp back to datetime
            if isinstance(data.get("timestamp"), str):
                timestamp = datetime.fromisoformat(data["timestamp"])
            else:
                timestamp = data.get("timestamp", datetime.now())

            # Convert correlation_id string back to UUID
            correlation_id = data.get("correlation_id")
            if isinstance(correlation_id, str):
                correlation_id = UUID(correlation_id)
            elif correlation_id is None:
                correlation_id = uuid4()

            return cls(
                event_type=data["event_type"],
                timestamp=timestamp,
                correlation_id=correlation_id,
                user_email=data.get("user_email", ""),
                metadata=data.get("metadata", {}),
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid event data: {e}")

    def __hash__(self) -> int:
        """Hash based on correlation_id and timestamp."""
        return hash((self.correlation_id, self.timestamp))
