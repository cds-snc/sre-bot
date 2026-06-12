"""Unit tests for ``packages.oncall_sync.settings``."""

import json
from pathlib import Path

import pytest

from packages.oncall_sync import settings as settings_module
from packages.oncall_sync.settings import (
    OnCallRotation,
    load_rotations,
)

_VALID_ROTATION = {
    "opsgenie_schedule_id": "abc",
    "opsgenie_rotation_name": "rot",
    "slack_handle": "oncall-x",
    "slack_name": "On-call X",
}


@pytest.mark.unit
def test_rotation_default_description() -> None:
    rotation = OnCallRotation(**_VALID_ROTATION)
    assert rotation.slack_description == "Auto-synced from OpsGenie"


@pytest.mark.unit
def test_load_rotations_returns_empty_when_resource_missing(
    monkeypatch, tmp_path
) -> None:
    class _MissingResource:
        @staticmethod
        def joinpath(_: str) -> "_MissingResource":
            return _MissingResource()

        @staticmethod
        def is_file() -> bool:
            return False

    monkeypatch.setattr(settings_module, "files", lambda _pkg: _MissingResource())

    assert load_rotations() == []


@pytest.mark.unit
def test_load_rotations_parses_valid_file(monkeypatch, tmp_path) -> None:
    rotations_file = tmp_path / "rotations.json"
    rotations_file.write_text(json.dumps([_VALID_ROTATION]))

    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    rotations = load_rotations()

    assert len(rotations) == 1
    assert rotations[0].slack_handle == "oncall-x"


@pytest.mark.unit
def test_load_rotations_raises_on_invalid_json(monkeypatch, tmp_path) -> None:
    (tmp_path / "rotations.json").write_text("{not json")
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_rotations()


@pytest.mark.unit
def test_load_rotations_rejects_non_list_top_level(monkeypatch, tmp_path) -> None:
    (tmp_path / "rotations.json").write_text('{"oops": true}')
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="must contain a JSON list"):
        load_rotations()


@pytest.mark.unit
def test_load_rotations_rejects_duplicate_slack_handles(monkeypatch, tmp_path) -> None:
    payload = [
        {**_VALID_ROTATION, "opsgenie_rotation_name": "rot1"},
        {**_VALID_ROTATION, "opsgenie_rotation_name": "rot2"},
    ]
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="duplicate slack_handle"):
        load_rotations()


class _FakeResources:
    """Minimal stand-in for ``importlib.resources.files(pkg)`` traversable."""

    def __init__(self, base: Path) -> None:
        self._base = base

    def joinpath(self, name: str) -> Path:
        return self._base / name
