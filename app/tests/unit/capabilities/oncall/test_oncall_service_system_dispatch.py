"""Unit tests for how the on-call service routes a lookup to its source by system.

The sources are Protocol fakes recording their calls; no network or file is touched. Assertions
are on which source answered, the results passed through unchanged and the unknown-system result.
"""

import pytest

from capabilities.oncall.domain import OnCallPerson, Schedule, ScheduleReference
from capabilities.oncall.interfaces import ScheduleSource
from capabilities.oncall.service import OnCallService
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus

pytestmark = pytest.mark.unit


class _Source(ScheduleSource):
    """Answers every lookup with a fixed person (or result) and records the references it was asked for."""

    def __init__(
        self, email: str, *, result: OperationResult[tuple[OnCallPerson, ...]] | None = None, raises: Exception | None = None
    ) -> None:
        self.email = email
        self.result = result
        self.raises = raises
        self.asked: list[tuple[ScheduleReference, str | None]] = []

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        self.asked.append((reference, rotation))
        if self.raises is not None:
            raise self.raises
        return self.result or OperationResult.success((OnCallPerson(email=self.email, account=None),))

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        return OperationResult.permanent_error(f"{self.email}:{horizon_weeks}", ErrorCode.UNSUPPORTED_OPERATION)

    async def list_schedules(self) -> OperationResult[tuple[ScheduleReference, ...]]:
        return OperationResult.success((ScheduleReference("a", self.email),))


def _service(a: _Source, b: _Source) -> OnCallService:
    return OnCallService({"a": a, "b": b})


async def test_each_system_is_answered_by_its_own_source() -> None:
    a, b = _Source("a@example.org"), _Source("b@example.org")
    service = _service(a, b)

    first = await service.on_call_now(ScheduleReference("a", "s1"), rotation="night")
    second = await service.on_call_now(ScheduleReference("b", "s2"))

    assert first.data == (OnCallPerson(email="a@example.org", account=None),)
    assert second.data == (OnCallPerson(email="b@example.org", account=None),)
    assert a.asked == [(ScheduleReference("a", "s1"), "night")]
    assert b.asked == [(ScheduleReference("b", "s2"), None)]


async def test_get_schedule_and_list_schedules_route_by_system() -> None:
    service = _service(_Source("a@example.org"), _Source("b@example.org"))

    schedule = await service.get_schedule(ScheduleReference("b", "s"), horizon_weeks=4)
    listed = await service.list_schedules("a")

    assert schedule.message == "b@example.org:4"
    assert listed.data == (ScheduleReference("a", "a@example.org"),)


@pytest.mark.parametrize("call", ["on_call_now", "get_schedule", "list_schedules"])
async def test_an_unknown_system_is_a_permanent_adapter_not_found(call: str) -> None:
    service = _service(_Source("a@example.org"), _Source("b@example.org"))

    if call == "on_call_now":
        result = await service.on_call_now(ScheduleReference("zzz", "s"))
    elif call == "get_schedule":
        result = await service.get_schedule(ScheduleReference("zzz", "s"))
    else:
        result = await service.list_schedules("zzz")

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.ADAPTER_NOT_FOUND


async def test_a_source_error_result_passes_through_unchanged() -> None:
    failing = OperationResult[tuple[OnCallPerson, ...]].transient_error("down", ErrorCode.SERVER_ERROR, retry_after=3)
    service = _service(_Source("a@example.org", result=failing), _Source("b@example.org"))

    result = await service.on_call_now(ScheduleReference("a", "s"))

    assert result == failing


async def test_an_unexpected_exception_from_a_source_propagates() -> None:
    service = _service(_Source("a@example.org", raises=RuntimeError("boom")), _Source("b@example.org"))

    with pytest.raises(RuntimeError, match="boom"):
        await service.on_call_now(ScheduleReference("a", "s"))
