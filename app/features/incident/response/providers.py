"""Feature-local dependency wiring for the incident response subdomain.

Resolves the core ports the response services write through, so the entry
points name one place to substitute them (decisions/testing.md, provider
substitution) and never import adapters.
"""

from capabilities.oncall.api import OnCallLookup, get_oncall_lookup
from contracts.coordination import ConditionalWriteStore
from features.incident.core.api import (
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    LegacyRolesReader,
    PlacementScheduleLookup,
    VideoCall,
    get_incident_conversation,
    get_incident_list_projection,
    get_incident_report,
    get_legacy_roles_reader,
    get_placement_schedule_lookup,
    get_video_call,
)
from features.incident.response.adapters.claims import ThreadedClaims
from features.incident.response.adapters.sentinel import SentinelArchiveEventSink
from features.incident.response.interfaces import ArchiveEventSink, Claims
from features.incident.response.service.declare import DeclarePolicy
from features.incident.response.settings import get_incident_response_settings


def incident_report() -> IncidentReport:
    """Return the process-wide ``IncidentReport``."""
    return get_incident_report()


def incident_list_projection() -> IncidentListProjection:
    """Return the process-wide ``IncidentListProjection``."""
    return get_incident_list_projection()


def incident_conversation() -> IncidentConversation:
    """Return the process-wide ``IncidentConversation``."""
    return get_incident_conversation()


def legacy_roles_reader() -> LegacyRolesReader:
    """Return the process-wide ``LegacyRolesReader`` (TODO(TASK-145.13): deleted with the legacy roles bridge)."""
    return get_legacy_roles_reader()


def archive_event_sink() -> ArchiveEventSink:
    """Return the sink the archived event is sent to (TODO(TASK-122): the audit capability's sink)."""
    return SentinelArchiveEventSink()


def video_call() -> VideoCall:
    """Return the process-wide ``VideoCall``."""
    return get_video_call()


def placement_schedule_lookup() -> PlacementScheduleLookup:
    """Return the placement schedule lookup (TODO(TASK-165.1): the product catalogue answers it)."""
    return get_placement_schedule_lookup()


def oncall_lookup() -> OnCallLookup:
    """Return the on-call capability's lookup."""
    return get_oncall_lookup()


def claims(store: ConditionalWriteStore) -> Claims:
    """Return claims over the scope's conditional-write store, failing closed."""
    return ThreadedClaims(store)


def declare_policy(*, production: bool) -> DeclarePolicy:
    """Return the declare policy from the ``[incident_response]`` slice."""
    return DeclarePolicy.from_settings(get_incident_response_settings(), production=production)
