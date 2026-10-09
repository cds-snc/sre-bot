"""Feature-local dependency wiring for the incident comms subdomain.

Resolves the default implementations of the Protocols the services depend on,
keeping the services and ``entrypoints/`` free of adapter (and therefore
``integrations``) imports.
"""

from functools import lru_cache

from features.incident.comms.adapters.copy_ready import CopyReadyPublisher
from features.incident.comms.adapters.text_generation import UnavailableTextGenerator, build_status_update_text_generator
from features.incident.comms.ports import StatusPagePublisher, TextGenerator


@lru_cache(maxsize=1)
def get_status_update_text_generator() -> TextGenerator:
    """Return the process-wide ``TextGenerator`` that drafts status updates."""
    return build_status_update_text_generator()


def text_generation_available() -> bool:
    """Whether the process ``TextGenerator`` is configured rather than the unavailable stand-in."""
    return not isinstance(get_status_update_text_generator(), UnavailableTextGenerator)


@lru_cache(maxsize=1)
def get_status_page_publisher() -> StatusPagePublisher:
    """Return the process-wide ``StatusPagePublisher`` that renders copy-ready text."""
    return CopyReadyPublisher()
