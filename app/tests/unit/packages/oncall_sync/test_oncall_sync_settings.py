"""Unit tests for ``packages.oncall_sync.settings``."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.oncall_sync import settings as settings_module
from packages.oncall_sync.settings import (
    OnCallRotationConfig,
    OnCallScheduleConfig,
    OnCallSyncSettings,
    get_oncall_sync_settings,
    load_schedules,
    load_sync_settings,
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


# ---------------------------------------------------------------------------
# Approved participant email domains (feature-owned settings slice)
# ---------------------------------------------------------------------------


def _write_rotations(monkeypatch, tmp_path: Path, payload: dict) -> None:
    (tmp_path / "rotations.json").write_text(json.dumps(payload))
    monkeypatch.setattr(settings_module, "files", lambda _pkg: _FakeResources(tmp_path))


@pytest.mark.unit
def test_approved_email_domains_defaults_to_empty(monkeypatch, tmp_path) -> None:
    _write_rotations(monkeypatch, tmp_path, {"schedules": [_VALID_SCHEDULE]})

    assert load_sync_settings().APPROVED_EMAIL_DOMAINS == []


@pytest.mark.unit
def test_approved_email_domains_default_to_empty_when_resource_missing(monkeypatch) -> None:
    class _MissingResource:
        @staticmethod
        def joinpath(_: str) -> _MissingResource:
            return _MissingResource()

        @staticmethod
        def is_file() -> bool:
            return False

    monkeypatch.setattr(settings_module, "files", lambda _pkg: _MissingResource())

    assert load_sync_settings().APPROVED_EMAIL_DOMAINS == []


@pytest.mark.unit
def test_approved_email_domains_loaded_from_rotations_resource(monkeypatch, tmp_path) -> None:
    _write_rotations(
        monkeypatch,
        tmp_path,
        {"approved_email_domains": ["example.com", "other.org"], "schedules": [_VALID_SCHEDULE]},
    )

    assert load_sync_settings().APPROVED_EMAIL_DOMAINS == ["example.com", "other.org"]


@pytest.mark.unit
def test_approved_email_domains_are_normalized(monkeypatch, tmp_path) -> None:
    _write_rotations(
        monkeypatch,
        tmp_path,
        {"approved_email_domains": ["Example.COM", " Other.Org ", "", "  "], "schedules": []},
    )

    assert load_sync_settings().APPROVED_EMAIL_DOMAINS == ["example.com", "other.org"]


@pytest.mark.unit
def test_approved_email_domains_reject_malformed_domain(monkeypatch, tmp_path) -> None:
    _write_rotations(monkeypatch, tmp_path, {"approved_email_domains": ["not a domain"], "schedules": []})

    with pytest.raises(ValidationError, match="invalid approved email domain"):
        load_sync_settings()


@pytest.mark.unit
def test_approved_email_domains_accept_name_or_alias() -> None:
    assert OnCallSyncSettings(APPROVED_EMAIL_DOMAINS=["Example.com"]).APPROVED_EMAIL_DOMAINS == ["example.com"]


@pytest.mark.unit
def test_get_oncall_sync_settings_is_singleton() -> None:
    get_oncall_sync_settings.cache_clear()
    try:
        assert get_oncall_sync_settings() is get_oncall_sync_settings()
    finally:
        get_oncall_sync_settings.cache_clear()


class _FakeResources:
    """Minimal stand-in for ``importlib.resources.files(pkg)`` traversable."""

    def __init__(self, base: Path) -> None:
        self._base = base

    def joinpath(self, name: str) -> Path:
        return self._base / name
