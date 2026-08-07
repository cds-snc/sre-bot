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
        self.calls: list[tuple[str, list[str]]] = []  # (handle, emails)

    def sync_user_group(self, handle: str, name: str, description: str, emails: Sequence[str]) -> None:
        if handle in self._raise_for:
            raise OnCallSyncError("target failed")
        self.calls.append((handle, list(emails)))


@pytest.mark.unit
def test_sync_all_updates_rotation_and_schedule_groups() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # Rotation groups: single email each; schedule group: union of both
    assert target.calls[:2] == [("a", ["alice@x.ca"]), ("b", ["bob@x.ca"])]
    assert target.calls[2] == ("oncall", ["alice@x.ca", "bob@x.ca"])


@pytest.mark.unit
def test_sync_all_skips_empty_rotation_in_schedule_group() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": None})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # Rotation b has no on-call user; schedule group gets only alice
    assert target.calls == [("a", ["alice@x.ca"]), ("oncall", ["alice@x.ca"])]


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_rotation_fails() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"}, raise_for={"a"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # b still gets its rotation group synced; schedule group is skipped
    assert [h for h, _ in target.calls] == ["b"]
    assert not any(h == "oncall" for h, _ in target.calls)


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_rotation_target_fails() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget(raise_for={"a"})

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    # a fails in target; schedule group is skipped
    assert not any(h == "oncall" for h, _ in target.calls)


@pytest.mark.unit
def test_sync_all_skips_schedule_group_when_all_rotations_empty() -> None:
    schedule = _schedule(handle="oncall", rotation_handles=["a", "b"])
    on_call = _FakeOnCall(emails={"a": None, "b": None})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, schedules=[schedule]).sync_all()

    assert target.calls == []


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
    assert target.calls == []


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

    # Each schedule has one rotation + one schedule group = 2 calls each, 4 total
    assert {h for h, _ in target.calls} == {"a", "b", "oncall-1", "oncall-2"}
