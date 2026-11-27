"""Feature-local dependency wiring for the incident response subdomain.

Resolves the core ports the response services write through, so the entry
points name one place to substitute them (decisions/testing.md, provider
substitution) and never import adapters.
"""

from capabilities.oncall.api import OnCallLookup, get_oncall_lookup
from contracts.coordination import ConditionalWriteStore
from contracts.languages import LanguagePolicy
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.api import (
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    LegacyRolesReader,
    PlacementScheduleLookup,
    VideoCall,
    build_incident_store,
    get_incident_conversation,
    get_incident_list_projection,
    get_incident_report,
    get_legacy_roles_reader,
    get_placement_schedule_lookup,
    get_video_call,
)
from features.incident.response.adapters.alert_acknowledgements import RecordStoreAlertAcknowledgements
from features.incident.response.adapters.claims import ThreadedClaims
from features.incident.response.adapters.sentinel import SentinelArchiveEventSink, SentinelDeclareEventSink
from features.incident.response.interfaces import AlertAcknowledgements, ArchiveEventSink, Claims, DeclareEventSink
from features.incident.response.service.declare import ChatSurface, DeclarePolicy, DeclarePorts
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


def video_call() -> VideoCall:
    """Return the process-wide ``VideoCall``, whose ``link`` renders the incident's call in show."""
    return get_video_call()


def legacy_roles_reader() -> LegacyRolesReader:
    """Return the process-wide ``LegacyRolesReader`` (TODO(TASK-145.13): deleted with the legacy roles bridge)."""
    return get_legacy_roles_reader()


def archive_event_sink() -> ArchiveEventSink:
    """Return the sink the archived event is sent to (TODO(TASK-122): the audit capability's sink)."""
    return SentinelArchiveEventSink()


def placement_schedule_lookup() -> PlacementScheduleLookup:
    """Return the placement schedule lookup (TODO(TASK-165.1): the product catalogue answers it)."""
    return get_placement_schedule_lookup()


def oncall_lookup() -> OnCallLookup:
    """Return the on-call capability's lookup."""
    return get_oncall_lookup()


def claims(store: ConditionalWriteStore) -> Claims:
    """Return claims over the scope's conditional-write store, failing closed."""
    return ThreadedClaims(store)


def declare_policy() -> DeclarePolicy:
    """Return the declare policy from the ``[incident_response]`` slice and ``[incident_core]``'s naming keys, read now."""
    core = get_incident_core_settings()
    return DeclarePolicy.from_settings(
        get_incident_response_settings(),
        production=not core.dev_conversation_names,
        conversation_name_attempts=core.conversation_name_attempts,
    )


def alert_acknowledgements(records: RecordStore) -> AlertAcknowledgements:
    """Return the alert acknowledgement counter over the scope's record store (TODO(TASK-37.6.2): the webhooks port)."""
    return RecordStoreAlertAcknowledgements(records)


def declare_event_sink() -> DeclareEventSink:
    """Return the sink the declare's events are sent to (TODO(TASK-122): the audit capability's sink)."""
    return SentinelDeclareEventSink()


def declare_ports(
    records: RecordStore, claims_store: ConditionalWriteStore, systems: ConfiguredSystems, languages: LanguagePolicy
) -> DeclarePorts:
    """Return the ports one declare runs through, built over the scope's stores; no chat surface without a Slack tenant."""
    slack_tenant = systems.tenants().get(WorkplaceSystem.SLACK)
    chat = ChatSurface(incident_conversation(), tenant=slack_tenant, languages=languages) if slack_tenant is not None else None
    return DeclarePorts(
        incidents=build_incident_store(records, systems, get_incident_core_settings()),
        reports=incident_report(),
        video_calls=video_call(),
        projection=incident_list_projection(),
        claims=claims(claims_store),
        schedules=placement_schedule_lookup(),
        oncall=oncall_lookup(),
        chat=chat,
    )
