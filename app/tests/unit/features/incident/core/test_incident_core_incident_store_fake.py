"""Behavior tests for the in-memory IncidentStore fake.

Consumer tests inject the fake in place of the records-backed store, so it
explicitly subclasses the Protocol (mypy checks it) and answers with the same
classifications. Open incidents are listed by declaration time as a stand-in
for the opened_at time the fake does not hold.
"""

from datetime import UTC, datetime, timedelta

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.domain import ConversationReference, Incident
from features.incident.core.store import IncidentStore

pytestmark = pytest.mark.unit

AT = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0TENANT", vendor_id="C0INCIDENT")


def _incident(incident_id: str, *, status: IncidentStatus = IncidentStatus.OPEN, hours: int = 0, **overrides: object) -> Incident:
    fields: dict[str, object] = {
        "id": incident_id,
        "title": f"Incident {incident_id}",
        "status": status,
        "declared_by": "U0DECLARER",
        "declared_at": AT + timedelta(hours=hours),
        "security_incident": False,
    }
    fields.update(overrides)
    return Incident(**fields)  # type: ignore[arg-type]


def test_the_fake_explicitly_subclasses_the_protocol() -> None:
    assert IncidentStore in InMemoryIncidentStore.__mro__
    assert isinstance(InMemoryIncidentStore(), IncidentStore)


def test_a_seeded_incident_is_read_back() -> None:
    store = InMemoryIncidentStore()
    incident = _incident("inc-1", security_incident=True)
    store.seed(incident)

    assert store.get("inc-1").data == incident
    assert store.read_security_flag("inc-1").data is True


@pytest.mark.parametrize("incident_id", ["missing", " "])
def test_a_missing_incident_is_not_an_incident(incident_id: str) -> None:
    store = InMemoryIncidentStore()

    for result in (store.get(incident_id), store.read_security_flag(incident_id)):
        assert result.status is OperationStatus.NOT_FOUND
        assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_another_tenant_sharing_the_channel_id_is_not_matched() -> None:
    store = InMemoryIncidentStore()
    other = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0OTHER", vendor_id="C0INCIDENT")
    store.seed(_incident("inc-theirs", conversation=other))

    assert store.find_by_conversation(CONVERSATION).error_code == ErrorCode.NOT_AN_INCIDENT


def test_open_defaults_to_the_status_and_lists_by_declaration_time() -> None:
    """Seeding open puts an incident in the open list; by default that follows its status, like the writers' open_bucket."""
    store = InMemoryIncidentStore()
    store.seed(_incident("late", hours=2))
    store.seed(_incident("early", hours=1))
    store.seed(_incident("closed", status=IncidentStatus.CLOSED))
    store.seed(_incident("not-indexed"), open=False)
    store.seed(_incident("closed-but-indexed", status=IncidentStatus.CLOSED, hours=3), open=True)

    result = store.list_open()

    assert result.data is not None
    assert [incident.id for incident in result.data] == ["early", "late", "closed-but-indexed"]
