"""Feature-local dependency wiring for the incident_summary package.

Resolves the default implementations of the Protocols the handlers depend on,
keeping ``platforms/`` free of adapter (and therefore ``integrations``) lookups.
"""

from functools import lru_cache

from packages.incident_summary.adapters.slack import build_incident_channel
from packages.incident_summary.service import IncidentChannelPort


@lru_cache(maxsize=1)
def get_incident_channel_port() -> IncidentChannelPort:
    """Return the process-wide Slack-backed ``IncidentChannelPort``."""
    return build_incident_channel()
