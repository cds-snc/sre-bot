"""Behavior tests for IncidentStore.set_roles: only the named roles change.

Each case runs on the real store over InMemoryRecordStore and on the fake; the
replay case counts writes on the real store.
"""

from collections.abc import Callable

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.store import IncidentStore
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import CountingRecordStore, declared_incident, record_incident_store

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """A real store or fake holding one created incident with a commander and an operations lead."""
    created = STORES[request.param]()
    assert created.create(declared_incident(INCIDENT_ID)).is_success
    assert created.set_roles(
        INCIDENT_ID, {IncidentRole.INCIDENT_COMMANDER: "U0IC", IncidentRole.OPERATIONS_LEAD: "U0OPS"}
    ).is_success
    return created


def test_a_role_is_set_and_the_others_stay(store: IncidentStore) -> None:
    """Naming the communications lead leaves the commander and operations lead as they were."""
    result = store.set_roles(INCIDENT_ID, {IncidentRole.COMMUNICATIONS_LEAD: "U0COMMS"})

    assert result.data is not None
    assert (result.data.incident_commander, result.data.operations_lead, result.data.communications_lead) == (
        "U0IC",
        "U0OPS",
        "U0COMMS",
    )
    assert store.get(INCIDENT_ID).data == result.data


def test_a_role_is_replaced(store: IncidentStore) -> None:
    """A new holder replaces the old one."""
    result = store.set_roles(INCIDENT_ID, {IncidentRole.INCIDENT_COMMANDER: "U0NEWIC"})

    assert result.data is not None
    assert result.data.incident_commander == "U0NEWIC"


def test_a_role_is_cleared_with_none(store: IncidentStore) -> None:
    """None unassigns the role; the others keep their holders."""
    result = store.set_roles(INCIDENT_ID, {IncidentRole.OPERATIONS_LEAD: None})

    assert result.data is not None
    assert (result.data.incident_commander, result.data.operations_lead) == ("U0IC", None)


def test_setting_the_same_holders_again_writes_nothing() -> None:
    """A replay finds every named role already held, so no update is sent."""
    records = CountingRecordStore()
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success
    roles: dict[IncidentRole, str | None] = {IncidentRole.POLICY_LEAD: "U0POLICY"}
    assert store.set_roles(INCIDENT_ID, roles).is_success
    writes = list(records.writes)

    assert store.set_roles(INCIDENT_ID, roles).is_success

    assert records.writes == writes


def test_a_missing_incident_is_not_an_incident(store: IncidentStore) -> None:
    """An unknown id is NOT_FOUND."""
    result = store.set_roles("inc-missing", {IncidentRole.POLICY_LEAD: "U0POLICY"})

    assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


@pytest.mark.parametrize(
    ("roles", "match"),
    [({}, "at least one"), ({IncidentRole.POLICY_LEAD: "  "}, "policy_lead"), ({"policy_lead": "U0"}, "IncidentRole")],
    ids=["nothing", "blank-holder", "bare-string-role"],
)
def test_roles_the_record_cannot_hold_raise(store: IncidentStore, roles: dict[IncidentRole, str | None], match: str) -> None:
    """Caller errors are refused before any read or write."""
    with pytest.raises(ValueError, match=match):
        store.set_roles(INCIDENT_ID, roles)
