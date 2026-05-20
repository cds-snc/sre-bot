"""Infrastructure event system facade.

The event system provides error-isolated, in-process dispatch for
cross-feature communication.
"""

from infrastructure.events.models import Event
from infrastructure.events.service import EventDispatcher, get_event_dispatcher

__all__ = [
    "Event",
    "EventDispatcher",
    "get_event_dispatcher",
]
