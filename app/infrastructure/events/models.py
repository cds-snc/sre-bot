"""Event models for infrastructure event system.

Provides generic Event base class and protocol for event handlers.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass
class Event(Generic[T]):
    """Base class for all events in the system.

    Events are immutable records of something that happened, used for
    audit trails, notifications, and cross-module communication.

    The generic parameter ``T`` is the typed payload carried in ``metadata``.
    """

    event_type: str
    """The type of event (e.g., 'group.member.added')."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the event occurred."""

    correlation_id: UUID = field(default_factory=uuid4)
    """Unique ID to track related events across the system."""

    user_email: str = ""
    """User who triggered the event."""

    metadata: Optional[T] = None
    """Typed payload for this event."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary.

        Typed payloads (dataclasses) are converted recursively via ``asdict``.
        Dict payloads are included as-is.  ``None`` metadata is serialized as
        an empty dict for downstream compatibility.

        Returns:
            Dictionary representation of the event with ISO format timestamp
            and UUID as string.
        """
        data = asdict(self)
        # Convert datetime to ISO format string
        data["timestamp"] = self.timestamp.isoformat()
        # Convert UUID to string
        data["correlation_id"] = str(self.correlation_id)
        # Normalise None metadata to empty dict for wire compatibility
        if data.get("metadata") is None:
            data["metadata"] = {}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event[Dict[str, Any]]":
        """Deserialize event from a dictionary (always produces dict metadata).

        Args:
            data: Dictionary with event fields.

        Returns:
            Event instance with ``metadata`` as a plain dict.

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

            return Event(  # type: ignore[return-value]
                event_type=data["event_type"],
                timestamp=timestamp,
                correlation_id=correlation_id,
                user_email=data.get("user_email", ""),
                metadata=data.get("metadata"),
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid event data: {e}")

    def __hash__(self) -> int:
        """Hash based on correlation_id and timestamp."""
        return hash((self.correlation_id, self.timestamp))
