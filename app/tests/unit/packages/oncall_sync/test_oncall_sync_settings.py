"""Unit tests for ``packages.oncall_sync.settings``."""

import json
from pathlib import Path

import pytest

from packages.oncall_sync import settings as settings_module
from packages.oncall_sync.settings import (
    OnCallRotationConfig,
    OnCallScheduleConfig,
    load_schedules,
)

_VALID_ROTATION = {
    "opsgenie_rotation_name": "rot",
    "slack_handle": "oncall-x",
    "slack_name": "On-call X",
}

_VALID_SCHEDULE = {
    "opsgenie_schedule_id": "abc",
    "slack_handle": "oncall",
    "slack_name": "On-call",
    "rotations": [_VALID_ROTATION],
}


@pytest.mark.unit
def test_rotation_config_default_description() -> None:
    rotation = OnCallRotationConfig(**_VALID_ROTATION)
    assert rotation.slack_description == "Auto-synced from OpsGenie"


@pytest.mark.unit
def test_schedule_config_default_description() -> None:
    schedule = OnCallScheduleConfig(**_VALID_SCHEDULE)
    assert schedule.slack_description == "Auto-synced from OpsGenie"


@pytest.mark.unit
def test_load_schedules_returns_empty_when_resource_missing(monkeypatch, tmp_path) -> None:
    class _MissingResource:
        @staticmethod
        def joinpath(_: str) -> _MissingResource:
            return _MissingResource()

        @staticmethod
        def is_file() -> bool:
            return False

    monkeypatch.setattr(settings_module, "files", lambda _pkg: _MissingResource())

    assert load_schedules() == []


@pytest.mark.unit
def test_load_schedules_parses_valid_file(monkeypatch, tmp_path) -> None:
    payload = {"schedules": [_VALID_SCHEDULE]}
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    schedules = load_schedules()

    assert len(schedules) == 1
    assert schedules[0].slack_handle == "oncall"
    assert len(schedules[0].rotations) == 1
    assert schedules[0].rotations[0].slack_handle == "oncall-x"


@pytest.mark.unit
def test_load_schedules_raises_on_invalid_json(monkeypatch, tmp_path) -> None:
    (tmp_path / "rotations.json").write_text("{not json")
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_schedules()


@pytest.mark.unit
def test_load_schedules_rejects_missing_schedules_key(monkeypatch, tmp_path) -> None:
    (tmp_path / "rotations.json").write_text('{"oops": true}')
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="'schedules' key"):
        load_schedules()


@pytest.mark.unit
def test_load_schedules_rejects_duplicate_schedule_handles(monkeypatch, tmp_path) -> None:
    payload = {
        "schedules": [
            {**_VALID_SCHEDULE, "rotations": []},
            {**_VALID_SCHEDULE, "rotations": []},
        ]
    }
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="duplicate slack_handle"):
        load_schedules()


@pytest.mark.unit
def test_load_schedules_rejects_duplicate_rotation_handles(monkeypatch, tmp_path) -> None:
    payload = {
        "schedules": [
            {
                **_VALID_SCHEDULE,
                "rotations": [
                    {**_VALID_ROTATION, "opsgenie_rotation_name": "rot1"},
                    {**_VALID_ROTATION, "opsgenie_rotation_name": "rot2"},
                ],
            }
        ]
    }
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="duplicate slack_handle"):
        load_schedules()


@pytest.mark.unit
def test_load_schedules_rejects_handle_collision_between_schedule_and_rotation(monkeypatch, tmp_path) -> None:
    payload = {
        "schedules": [
            {
                **_VALID_SCHEDULE,
                "slack_handle": "oncall-x",  # same as the rotation handle
                "rotations": [_VALID_ROTATION],
            }
        ]
    }
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="duplicate slack_handle"):
        load_schedules()


class _FakeResources:
    """Minimal stand-in for ``importlib.resources.files(pkg)`` traversable."""

    def __init__(self, base: Path) -> None:
        self._base = base

    def joinpath(self, name: str) -> Path:
        return self._base / name
