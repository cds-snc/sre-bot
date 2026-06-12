"""Unit tests for the platform-neutral ``OnCallSyncService`` orchestrator."""

from typing import Any

import pytest

from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.service import OnCallSyncService
from packages.oncall_sync.settings import OnCallRotation


def _rotation(handle: str = "oncall-x") -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id="abc",
        opsgenie_rotation_name="rot",
        slack_handle=handle,
        slack_name="On-call X",
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
        self.calls: list[tuple[OnCallRotation, str]] = []

    def sync_user_group(self, rotation: OnCallRotation, on_call_email: str) -> None:
        if rotation.slack_handle in self._raise_for:
            raise OnCallSyncError("target failed")
        self.calls.append((rotation, on_call_email))


@pytest.mark.unit
def test_sync_all_updates_target_for_each_rotation_with_on_call() -> None:
    rotations = [_rotation("a"), _rotation("b")]
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, rotations=rotations).sync_all()

    assert [c[0].slack_handle for c in target.calls] == ["a", "b"]
    assert [c[1] for c in target.calls] == ["alice@x.ca", "bob@x.ca"]


@pytest.mark.unit
def test_sync_all_skips_target_when_rotation_has_no_on_call() -> None:
    on_call = _FakeOnCall(emails={"a": None})
    target = _FakeTarget()

    OnCallSyncService(
        on_call=on_call, target=target, rotations=[_rotation("a")]
    ).sync_all()

    assert target.calls == []


@pytest.mark.unit
def test_sync_all_isolates_failure_in_one_rotation() -> None:
    rotations = [_rotation("a"), _rotation("b")]
    on_call = _FakeOnCall(
        emails={"a": "alice@x.ca", "b": "bob@x.ca"},
        raise_for={"a"},
    )
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, rotations=rotations).sync_all()

    # b still processed despite a failing.
    assert [c[0].slack_handle for c in target.calls] == ["b"]


@pytest.mark.unit
def test_sync_all_isolates_target_failure() -> None:
    rotations = [_rotation("a"), _rotation("b")]
    on_call = _FakeOnCall(emails={"a": "alice@x.ca", "b": "bob@x.ca"})
    target = _FakeTarget(raise_for={"a"})

    OnCallSyncService(on_call=on_call, target=target, rotations=rotations).sync_all()

    # On-call provider was called for both; target was attempted for both
    # but only b succeeded (a raised internally).
    assert [c.slack_handle for c in on_call.calls] == ["a", "b"]


@pytest.mark.unit
def test_sync_all_noop_when_no_rotations() -> None:
    on_call = _FakeOnCall()
    target = _FakeTarget()

    OnCallSyncService(on_call=on_call, target=target, rotations=[]).sync_all()

    assert on_call.calls == []
    assert target.calls == []


@pytest.mark.unit
def test_service_accepts_any_iterable_of_rotations() -> None:
    on_call = _FakeOnCall(emails={"a": "alice@x.ca"})
    target = _FakeTarget()

    def _generator() -> Any:
        yield _rotation("a")

    OnCallSyncService(on_call=on_call, target=target, rotations=_generator()).sync_all()

    assert len(target.calls) == 1
