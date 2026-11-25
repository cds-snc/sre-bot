"""The service scope the response entry points open for one incident command, and the instance language policy."""

from collections.abc import Generator
from contextlib import contextmanager

from contracts.languages import LanguagePolicy
from contracts.records import RecordStore
from contracts.services import ServiceScopeOpener
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.api import ConversationReference, IncidentStore, build_incident_store


@contextmanager
def incident_scope(scopes: ServiceScopeOpener, channel_id: str) -> Generator[tuple[IncidentStore, ConversationReference]]:
    """Open one service scope; yield the incident store built in it and the channel's conversation reference.

    The Slack tenant is present, since the entry points register nothing without it.
    """
    with scopes.create_scope() as services:
        systems = services.get(ConfiguredSystems)
        incidents = build_incident_store(services.get(RecordStore), systems, get_incident_core_settings())
        tenant = systems.tenants()[WorkplaceSystem.SLACK]
        yield incidents, ConversationReference(system=WorkplaceSystem.SLACK, tenant=tenant, vendor_id=channel_id)


def language_policy(scopes: ServiceScopeOpener) -> LanguagePolicy:
    """Resolve the instance language policy (decisions/languages.md); it holds no per-scope state."""
    with scopes.create_scope() as services:
        return services.get(LanguagePolicy)


def shared_languages(policy: LanguagePolicy, conversation: ConversationReference) -> tuple[str, ...]:
    """The languages, in order, of a message posted to ``conversation``."""
    return policy.shared_languages(system=conversation.system, tenant=conversation.tenant, conversation_id=conversation.vendor_id)
