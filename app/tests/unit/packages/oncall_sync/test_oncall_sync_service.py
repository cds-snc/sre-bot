"""Unit tests for the platform-neutral ``OnCallSyncService`` orchestrator."""

from collections.abc import Sequence

import pytest

from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.service import OnCallSyncService
from packages.oncall_sync.settings import (
    OnCallRotation,
    OnCallRotationConfig,
    OnCallScheduleConfig,
)


def _rotation_config(handle: str = "oncall-x", name: str = "rot") -> OnCallRotationConfig:
    return OnCallRotationConfig(
        opsgenie_rotation_name=name,
        slack_handle=handle,
        slack_name=f"On-call {handle}",
    )


def _schedule(
    handle: str = "oncall",
    rotation_handles: list[str] | None = None,
) -> OnCallScheduleConfig:
    rotations = [_rotation_config(h) for h in (rotation_handles or ["oncall-x"])]
    return OnCallScheduleConfig(
        opsgenie_schedule_id="abc",
        slack_handle=handle,
        slack_name="On-call",
        rotations=rotations,
    )


class _FakeOnCall:
    def __init__(
        self,
        *,
        emails: dict[str, str | None] | None = None,
        raise_for: set[str] | None = None,
    ) -> None:
        self._emails = emails or {}
        self._raise_for = raise_for or set()
        self.calls: list[OnCallRotation] = []

    def get_current_on_call_email(self, rotation: OnCallRotation) -> str | None:
        self.calls.append(rotation)
        if rotation.slack_handle in self._raise_for:
            raise OnCallSyncError("oncall lookup failed")
        return self._emails.get(rotation.slack_handle)


class _FakeTarget:
    def __init__(self, *, raise_for: set[str] | None = None) -> None:
        self._raise_for = raise_for or set()
        self.rotation_calls: list[tuple[OnCallRotation, str]] = []
        self.schedule_calls: list[tuple[OnCallScheduleConfig, list[str]]] = []

    def sync_user_group(self, rotation: OnCallRotation, on_call_email: str) -> None:
        if rotation.slack_handle in self._raise_for:
            raise OnCallSyncError("target failed")
        self.rotation_calls.append((rotation, on_call_email))

    def sync_schedule_user_group(
        self, schedule: OnCallScheduleConfig, on_call_emails: Sequence[str]
    ) -> None:
        if schedule.slack_handle in self._raise_for:
            raise OnCallSyncError("schedule target failed")
        self.schedule_calls.append((schedule, list(on_call_emails)))


@pytest.mark.unit
def test_sync_all_updates_rotation_and_schedule_groups() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    assert [c[0].slack_handle for c in target.rotation_calls] == ["a", "b"]
    assert [c[1] for c in target.rotation_calls] == ["alice@x.ca", "bob@x.ca"]
    assert len(target.schedule_calls) == 1
    assert target.schedule_calls[0][0].slack_handle == "oncall"
    assert sorted(target.schedule_calls[0][1]) == ["alice@x.ca", "bob@x.ca"]


@pytest.mark.unit
def test_sync_all_skips_empty_rotation_in_schedule_group() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": None})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # Rotation b has no on-call user; schedule group gets only alice
    assert len(target.schedule_calls) == 1
    assert target.schedule_calls[0][1] == ["alice@x.ca"]


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_rotation_fails() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"}, raise_for={"a"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # b still gets its rotation group synced; schedule group is skipped
    assert [c[0].slack_handle for c in target.rotation_calls] == ["b"]
    assert target.schedule_calls == []


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_rotation_target_fails() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget(raise_for={"a"})

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # a fails in target; schedule group is skipped
    assert target.schedule_calls == []


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_all_rotations_empty() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": None, "b": None})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    assert target.rotation_calls == []
    assert target.schedule_calls == []


@pytest.mark.unit
def test_sync_all_schedule_group_failure_is_isolated() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca"})
    target = _FakeTarget(raise_for={"oncall"})

    # Should not raise; schedule group failure is caught and logged
    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()


@pytest.mark.unit
def test_sync_all_noop_when_no_schedules() -> None:
    on_call = _FakeOnCall()
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[]).sync_all()

    assert on_call.calls == []
    assert target.rotation_calls == []
    assert target.schedule_calls == []


@pytest.mark.unit
def test_rotation_resolved_with_parent_schedule_id() -> None:
    """The flat OnCallRotation passed to adapters carries the schedule's OpsGenie ID."""
    schedule = _schedule(handle="oncall", rotation_handles=["a"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    assert on_call.calls[0].opsgenie_schedule_id == "abc"
    assert on_call.calls[0].slack_handle == "a"


@pytest.mark.unit
def test_multiple_schedules_are_each_synced() -> None:
    schedules = [
        _schedule(handle="oncall-1", rotation_handles=["a"]),
        _schedule(handle="oncall-2", rotation_handles=["b"]),
    ]
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=schedules).sync_all()

    assert len(target.schedule_calls) == 2
    schedule_handles = {c[0].slack_handle for c in target.schedule_calls}
    assert schedule_handles == {"oncall-1", "oncall-2"}
