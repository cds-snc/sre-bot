"""Unit tests for loading the self-managed rotation files and answering from them.

The loader runs over real JSON files in a pytest ``tmp_path`` directory (the filesystem is its
edge). The source is built from loaded schedules with a fixed clock. Assertions are on the
schedules produced, the error messages (kept from the files' original format) and the results.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from capabilities.oncall.adapters.rotations import RotationsSource, load_rotation_schedules
from capabilities.oncall.domain import ROTATIONS, Account, OnCallPerson, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus

pytestmark = pytest.mark.unit

START = datetime(2026, 1, 5, 9, tzinfo=UTC)


def _write(directory: Path, name: str, **overrides: Any) -> None:
    payload: dict[str, Any] = {
        "slack-usergroup-handle": "oncall-a",
        "slack-usergroup-name": "On-call A",
        "members": ["U1", "U2"],
    }
    payload.update(overrides)
    (directory / name).write_text(json.dumps(payload))


def _slack(member_id: str) -> OnCallPerson:
    return OnCallPerson(email=None, account=Account("slack", None, member_id))


def test_a_minimal_file_maps_to_a_schedule_of_one_weekly_rotation(tmp_path: Path) -> None:
    _write(tmp_path, "a.json")

    (schedule,) = load_rotation_schedules(tmp_path)

    assert schedule.reference == ScheduleReference(ROTATIONS, "oncall-a")
    assert schedule.name == "On-call A"
    (rotation,) = schedule.rotations
    assert rotation.members == (_slack("U1"), _slack("U2"))
    assert rotation.weeks_per_shift == 1


def test_a_custom_file_keeps_its_shift_length_and_start(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", weeks_per_shift=2, rotation_start="2026-02-02T09:00:00+00:00")

    (schedule,) = load_rotation_schedules(tmp_path)

    assert schedule.rotations[0].weeks_per_shift == 2
    assert schedule.rotations[0].start == datetime(2026, 2, 2, 9, tzinfo=UTC)


def test_a_missing_directory_means_no_rotations(tmp_path: Path) -> None:
    assert load_rotation_schedules(tmp_path / "absent") == ()


def test_files_load_in_name_order_and_other_files_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "b.json", **{"slack-usergroup-handle": "b"})
    _write(tmp_path, "a.json", **{"slack-usergroup-handle": "a"})
    (tmp_path / "notes.txt").write_text("not a rotation")

    schedules = load_rotation_schedules(tmp_path)

    assert [schedule.reference.id for schedule in schedules] == ["a", "b"]


def test_duplicate_handles_fail_the_load_naming_them(tmp_path: Path) -> None:
    _write(tmp_path, "a.json")
    _write(tmp_path, "b.json")

    with pytest.raises(ValueError, match=r"duplicate slack-usergroup-handle values: \['oncall-a'\]"):
        load_rotation_schedules(tmp_path)


def test_invalid_json_fails_the_load_naming_the_file(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json")

    with pytest.raises(ValueError, match=r"Invalid JSON in rotation_files/broken\.json"):
        load_rotation_schedules(tmp_path)


def test_a_naive_rotation_start_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", rotation_start="2026-02-02T09:00:00")

    with pytest.raises(ValidationError, match="rotation_start must include a UTC offset"):
        load_rotation_schedules(tmp_path)


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", surprise=1)

    with pytest.raises(ValidationError, match="surprise"):
        load_rotation_schedules(tmp_path)


def test_a_handle_that_is_not_slack_safe_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", **{"slack-usergroup-handle": "Not Safe"})

    with pytest.raises(ValidationError, match="Slack-handle-safe"):
        load_rotation_schedules(tmp_path)


async def test_the_source_answers_who_is_on_call_from_the_loaded_files(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", rotation_start=START.isoformat())
    source = RotationsSource(load_rotation_schedules(tmp_path), clock=lambda: START + timedelta(weeks=1, hours=1))

    result = await source.on_call_now(ScheduleReference(ROTATIONS, "oncall-a"))

    assert result.status is OperationStatus.SUCCESS
    assert result.data == (_slack("U2"),)


async def test_the_source_returns_the_schedule_with_its_shifts(tmp_path: Path) -> None:
    _write(tmp_path, "a.json", rotation_start=START.isoformat())
    source = RotationsSource(load_rotation_schedules(tmp_path), clock=lambda: START)

    result = await source.get_schedule(ScheduleReference(ROTATIONS, "oncall-a"), horizon_weeks=2)

    assert result.data is not None
    assert [shift.person for shift in result.data.shifts] == [_slack("U1"), _slack("U2")]


async def test_the_source_lists_the_loaded_references(tmp_path: Path) -> None:
    _write(tmp_path, "a.json")
    source = RotationsSource(load_rotation_schedules(tmp_path))

    result = await source.list_schedules()

    assert result.data == (ScheduleReference(ROTATIONS, "oncall-a"),)


async def test_an_unknown_rotation_is_not_found() -> None:
    source = RotationsSource(())

    result = await source.on_call_now(ScheduleReference(ROTATIONS, "nope"))

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_FOUND


def test_the_packaged_default_directory_loads_the_rotation_files_shipped_with_the_capability() -> None:
    schedules = load_rotation_schedules()

    references = [schedule.reference for schedule in schedules]
    assert ScheduleReference(ROTATIONS, "canadalogin-website-atc") in references
