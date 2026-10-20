"""Incident records and stores for tests of the incident subdomains.

Each incident sits on a Slack conversation under one tenant, so a test that
resolves a conversation through ``InMemoryIncidentStore`` exercises the same
system, tenant and channel match the real store applies.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.domain import ConversationReference, Incident
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.services import FakeServiceScopeOpener

SLACK_TENANT = "T0SLACK"
DECLARED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def slack_conversation(channel_id: str, *, tenant: str = SLACK_TENANT) -> ConversationReference:
    """The Slack conversation reference of ``channel_id`` under ``tenant``."""
    return ConversationReference(system=WorkplaceSystem.SLACK, tenant=tenant, vendor_id=channel_id)


def incident_on(
    channel_id: str,
    incident_id: str,
    *,
    tenant: str = SLACK_TENANT,
    security_incident: bool = False,
) -> Incident:
    """An open incident whose conversation is ``channel_id`` under ``tenant``."""
    return Incident(
        id=incident_id,
        title=f"Incident {incident_id}",
        status=IncidentStatus.OPEN,
        declared_by="U0DECLARER",
        declared_at=DECLARED_AT,
        security_incident=security_incident,
        conversation=slack_conversation(channel_id, tenant=tenant),
    )


def incident_store_with(*incidents: Incident) -> InMemoryIncidentStore:
    """An in-memory incident store seeded with ``incidents``."""
    store = InMemoryIncidentStore()
    for incident in incidents:
        store.seed(incident)
    return store


class FakeConfiguredSystems(ConfiguredSystems):
    """Configured systems fixed at construction."""

    def __init__(self, tenants: Mapping[WorkplaceSystem, str]) -> None:
        self._tenants = dict(tenants)

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        """Return the tenant id of each configured system."""
        return self._tenants


def incident_scopes(
    records: RecordStore | None = None,
    *,
    tenants: Mapping[WorkplaceSystem, str] | None = None,
) -> FakeServiceScopeOpener:
    """A scope opener resolving the RecordStore and ConfiguredSystems an incident entry point needs.

    ``records`` defaults to an empty ``InMemoryRecordStore``; ``tenants``
    defaults to Slack configured under ``SLACK_TENANT``.
    """
    return FakeServiceScopeOpener(
        {
            RecordStore: records if records is not None else InMemoryRecordStore(),
            ConfiguredSystems: FakeConfiguredSystems({WorkplaceSystem.SLACK: SLACK_TENANT} if tenants is None else tenants),
        }
    )
