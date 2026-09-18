"""Unit tests for self-managed rotation configuration."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.user_rotations import settings as settings_module
from packages.user_rotations.settings import DEFAULT_ROTATION_START, RotationConfig, load_rotations

_VALID_ROTATION = {
    "slack-usergroup-handle": "fielding-questions",
    "slack-usergroup-name": "Fielding questions",
    "members": ["U1", "U2"],
}


class _FakeResources:
    def __init__(self, base: Path) -> None:
        self._base = base

    def joinpath(self, name: str) -> Path:
        return self._base / name


def _write_rotation(tmp_path: Path, name: str, payload: dict) -> None:
    rotations_path = tmp_path / "rotations"
    rotations_path.mkdir(exist_ok=True)
    (rotations_path / name).write_text(json.dumps(payload))


@pytest.mark.unit
def test_rotation_config_accepts_minimal_document_with_default_timing() -> None:
    rotation = RotationConfig.model_validate(_VALID_ROTATION)

    assert rotation.slack_usergroup_handle == "fielding-questions"
    assert rotation.slack_usergroup_name == "Fielding questions"
    assert rotation.rotation_type == "weekly"
    assert rotation.weeks_per_shift == 1
    assert rotation.rotation_start == DEFAULT_ROTATION_START


@pytest.mark.unit
def test_rotation_config_accepts_custom_weekly_shift_and_start() -> None:
    rotation = RotationConfig.model_validate(
        {
            **_VALID_ROTATION,
            "weeks_per_shift": 2,
            "rotation_start": "2026-09-14T09:00:00-04:00",
        }
    )

    assert rotation.weeks_per_shift == 2
    assert rotation.rotation_start == datetime(2026, 9, 14, 13, tzinfo=UTC)


@pytest.mark.unit
def test_load_rotations_returns_empty_when_directory_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    assert load_rotations() == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({**_VALID_ROTATION, "rotation_type": "monthly"}, "rotation_type"),
        ({**_VALID_ROTATION, "weeks_per_shift": 0}, "weeks_per_shift"),
        ({**_VALID_ROTATION, "rotation_start": "not-a-date"}, "rotation_start"),
        ({**_VALID_ROTATION, "members": []}, "members"),
        ({**_VALID_ROTATION, "members": ["U1", " "]}, "members"),
        ({**_VALID_ROTATION, "slack-usergroup-handle": "not a handle"}, "slack-usergroup-handle"),
        ({key: value for key, value in _VALID_ROTATION.items() if key != "slack-usergroup-name"}, "slack-usergroup-name"),
    ],
)
def test_rotation_config_rejects_invalid_configuration(payload: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        RotationConfig.model_validate(payload)


@pytest.mark.unit
def test_load_rotations_rejects_duplicate_handles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_rotation(tmp_path, "first.json", _VALID_ROTATION)
    _write_rotation(tmp_path, "second.json", _VALID_ROTATION)
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="duplicate slack-usergroup-handle"):
        load_rotations()


@pytest.mark.unit
def test_load_rotations_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rotations_path = tmp_path / "rotations"
    rotations_path.mkdir()
    (rotations_path / "invalid.json").write_text("{not json")
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_rotations()
