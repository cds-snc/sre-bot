"""The declare's provider builders: the ports over the scope's stores, the counter and the event sink.

The core providers the builder reads are replaced by in-memory fakes; the record and
claims stores are in-memory. Assertions are on what the declare will run through: the
chat surface exists exactly when Slack is configured, under its tenant and with the
scope's language policy, and the Sentinel event sink sends the legacy envelope with
the ids-only message.
"""

from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation
from features.incident.response import providers
from features.incident.response.adapters.alert_acknowledgements import RecordStoreAlertAcknowledgements
from features.incident.response.adapters.sentinel import SentinelDeclareEventSink
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from infrastructure.records.in_memory import InMemoryRecordStore
from integrations.sentinel import client as sentinel_client
from server.languages.policy import ConfiguredLanguagePolicy
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT, FakeConfiguredSystems

pytestmark = pytest.mark.unit

LANGUAGES = ConfiguredLanguagePolicy(shared=("fr-FR", "en-US"), supported=("en-US", "fr-FR"))
CLAIMS = InMemoryConditionalWriteStore(record_ttl_seconds=60, in_progress_ttl_seconds=60)


def test_with_slack_configured_the_ports_carry_a_chat_surface_under_its_tenant_and_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT)
    monkeypatch.setattr(providers, "incident_conversation", lambda: conversations)
    systems = FakeConfiguredSystems({WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT})

    ports = providers.declare_ports(InMemoryRecordStore(), CLAIMS, systems, LANGUAGES)

    assert ports.chat is not None
    assert (ports.chat.conversations, ports.chat.tenant, ports.chat.languages) == (conversations, SLACK_TENANT, LANGUAGES)


def test_without_slack_the_ports_have_no_chat_surface() -> None:
    systems = FakeConfiguredSystems({WorkplaceSystem.GOOGLE: GOOGLE_TENANT})

    assert providers.declare_ports(InMemoryRecordStore(), CLAIMS, systems, LANGUAGES).chat is None


def test_the_counter_and_the_sink() -> None:
    assert isinstance(providers.alert_acknowledgements(InMemoryRecordStore()), RecordStoreAlertAcknowledgements)
    assert isinstance(providers.declare_event_sink(), SentinelDeclareEventSink)


async def test_the_sentinel_sink_sends_the_legacy_envelope_with_the_ids_only(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Any] = []
    monkeypatch.setattr(sentinel_client, "send_event", lambda payload: sent.append(payload) or True)

    await SentinelDeclareEventSink().send("incident_called", {"user_id": "U0", "view_id": "V0"})

    assert sent == [{"event": "incident_called", "message": {"user_id": "U0", "view_id": "V0"}}]
