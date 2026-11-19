"""Feature-local dependency wiring for the incident comms subdomain.

Resolves the default implementations of the Protocols the services depend on,
keeping the services and ``entrypoints/`` free of adapter imports. Text generation
is the capability's: the services import ``capabilities.text_generation.api``.
"""

from functools import lru_cache

from features.incident.comms.adapters.copy_ready import CopyReadyPublisher
from features.incident.comms.interfaces import StatusPagePublisher


@lru_cache(maxsize=1)
def get_status_page_publisher() -> StatusPagePublisher:
    """Return the process-wide ``StatusPagePublisher`` that renders copy-ready text."""
    return CopyReadyPublisher()
