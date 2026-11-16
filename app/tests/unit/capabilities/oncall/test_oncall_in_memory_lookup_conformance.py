"""Conformance tests for the in-memory on-call lookup against the real service's rules.

The fake and the real service (over a rotations source and a stubbed Opsgenie edge) answer the
same questions; assertions are on the shared observable rules per system. The enrolment test
keeps the fake registered with the fake-coverage rule.
"""

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from bin.check_fake_coverage import find_covered_protocols, find_fakes
from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from capabilities.oncall.adapters.opsgenie import OpsgenieSource
from capabilities.oncall.adapters.rotations import RotationsSource
from capabilities.oncall.api import OnCallLookup
from capabilities.oncall.domain import OPSGENIE, ROTATIONS, Account, OnCallPerson, Rotation, Schedule, ScheduleReference
from capabilities.oncall.service import OnCallService
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.opsgenie.settings import OpsGenieSettings, OpsGenieTenant

pytestmark = pytest.mark.unit

START = datetime(2026, 1, 5, 9, tzinfo=UTC)
ROTATION_REF = ScheduleReference(ROTATIONS, "oncall-a")
OPSGENIE_REF = ScheduleReference(OPSGENIE, "sched-1")
SLACK_PERSON = OnCallPerson(email=None, account=Account("slack", None, "U1"))
EMAIL_PERSON = OnCallPerson(email="a@example.org", account=None)
SCHEDULE = Schedule(ROTATION_REF, "On-call A", (Rotation("On-call A", (SLACK_PERSON,), 1, START),), ())


def _settings() -> OpsGenieSettings:
    return OpsGenieSettings.model_construct(
        tenant=OpsGenieTenant(api_url="https://api.opsgenie.com"),
        integrations_key=SecretStr("k"),
        timeout_seconds=5.0,
        connect_retries=0,
    )


def _opsgenie_client(settings: OpsGenieSettings) -> httpx.AsyncClient:
    body = {"data": {"onCallParticipants": [{"name": "a@example.org"}]}}
    return httpx.AsyncClient(
        base_url="https://api.opsgenie.com", transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )


def _real() -> OnCallLookup:
    rotations = RotationsSource((SCHEDULE,), clock=lambda: START)
    opsgenie = OpsgenieSource(settings=_settings, client_factory=_opsgenie_client)
    return OnCallService({ROTATIONS: rotations, OPSGENIE: opsgenie})


def _fake() -> OnCallLookup:
    return InMemoryOnCallLookup(
        people={ROTATION_REF: (SLACK_PERSON,), OPSGENIE_REF: (EMAIL_PERSON,)},
        schedules={ROTATION_REF: SCHEDULE},
    )


@pytest.fixture(params=[_real, _fake], ids=["service", "in-memory"])
def lookup(request: pytest.FixtureRequest) -> OnCallLookup:
    return request.param()


async def test_both_systems_answer_who_is_on_call(lookup: OnCallLookup) -> None:
    rotations = await lookup.on_call_now(ROTATION_REF)
    opsgenie = await lookup.on_call_now(OPSGENIE_REF)

    assert rotations.data == (SLACK_PERSON,)
    assert opsgenie.data == (EMAIL_PERSON,)


async def test_an_unknown_system_is_adapter_not_found(lookup: OnCallLookup) -> None:
    result = await lookup.on_call_now(ScheduleReference("goalert", "s"))

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.ADAPTER_NOT_FOUND


async def test_an_opsgenie_schedule_is_unsupported(lookup: OnCallLookup) -> None:
    result = await lookup.get_schedule(OPSGENIE_REF)

    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION


async def test_list_schedules_answers_rotations_and_nothing_for_opsgenie(lookup: OnCallLookup) -> None:
    assert (await lookup.list_schedules(ROTATIONS)).data == (ROTATION_REF,)
    assert (await lookup.list_schedules(OPSGENIE)).data == ()


def test_the_fake_is_enrolled_in_the_fake_coverage_rule() -> None:
    assert "capabilities/oncall/api.py:OnCallLookup" in find_covered_protocols()
    assert "OnCallLookup" in find_fakes()
