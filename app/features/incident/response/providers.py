"""Feature-local dependency wiring for the incident response subdomain.

Resolves the core ports the response services write through, so the entry
points name one place to substitute them (decisions/testing.md, provider
substitution) and never import adapters.
"""

from features.incident.core.api import (
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    LegacyRolesReader,
    VideoCall,
    get_incident_conversation,
    get_incident_list_projection,
    get_incident_report,
    get_legacy_roles_reader,
    get_video_call,
)
from features.incident.response.adapters.sentinel import SentinelArchiveEventSink
from features.incident.response.interfaces import ArchiveEventSink


def incident_report() -> IncidentReport:
    """Return the process-wide ``IncidentReport``."""
    return get_incident_report()


def incident_list_projection() -> IncidentListProjection:
    """Return the process-wide ``IncidentListProjection``."""
    return get_incident_list_projection()


def incident_conversation() -> IncidentConversation:
    """Return the process-wide ``IncidentConversation``."""
    return get_incident_conversation()


def video_call() -> VideoCall:
    """Return the process-wide ``VideoCall``, whose ``link`` renders the incident's call in show."""
    return get_video_call()


def legacy_roles_reader() -> LegacyRolesReader:
    """Return the process-wide ``LegacyRolesReader`` (TODO(TASK-145.13): deleted with the legacy roles bridge)."""
    return get_legacy_roles_reader()


def archive_event_sink() -> ArchiveEventSink:
    """Return the sink the archived event is sent to (TODO(TASK-122): the audit capability's sink)."""
    return SentinelArchiveEventSink()
