"""Unit tests for self-managed rotation selection and current assignments."""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from packages.user_rotations.service import UserRotationsService, whos_on
from packages.user_rotations.settings import RotationConfig


def _rotation(*, members: list[str] | None = None, weeks_per_shift: int = 1) -> RotationConfig:
    return RotationConfig(
        slack_usergroup_handle="fielding-questions",
        slack_usergroup_name="Fielding questions",
        members=members or ["U1", "U2"],
        rotation_start=datetime(2026, 9, 14, 9, tzinfo=UTC),
        weeks_per_shift=weeks_per_shift,
    )


@pytest.mark.unit
def test_whos_on_selects_first_member_at_rotation_start() -> None:
    rotation = _rotation()

    assert whos_on(rotation, t=rotation.rotation_start) == "U1"


@pytest.mark.unit
def test_whos_on_rotates_after_configured_shift_length() -> None:
    rotation = _rotation(weeks_per_shift=2)

    assert whos_on(rotation, t=rotation.rotation_start + timedelta(weeks=2)) == "U2"


@pytest.mark.unit
def test_get_current_rotations_returns_each_rotation_and_its_current_slack_user() -> None:
    first = _rotation()
    second = first.model_copy(
        update={"slack_usergroup_handle": "release-duty", "slack_usergroup_name": "Release duty", "members": ["U3"]}
    )

    current_rotations = UserRotationsService(rotations=[first, second]).get_current_rotations(t=first.rotation_start)

    assert [
        (rotation.slack_usergroup_handle, rotation.slack_usergroup_name, rotation.slack_user_id) for rotation in current_rotations
    ] == [
        (
            "fielding-questions",
            "Fielding questions",
            "U1",
        ),
        ("release-duty", "Release duty", "U3"),
    ]


@pytest.mark.unit
def test_get_rotation_shifts_returns_the_active_and_next_twelve_weeks() -> None:
    rotation = _rotation()

    with freeze_time(rotation.rotation_start + timedelta(days=3)):
        shifts = UserRotationsService(rotations=[rotation]).get_rotation_shifts("fielding-questions")

    assert [(shift.slack_user_id, shift.start, shift.end) for shift in shifts] == [
        ("U1", rotation.rotation_start, rotation.rotation_start + timedelta(weeks=1)),
        ("U2", rotation.rotation_start + timedelta(weeks=1), rotation.rotation_start + timedelta(weeks=2)),
        ("U1", rotation.rotation_start + timedelta(weeks=2), rotation.rotation_start + timedelta(weeks=3)),
        ("U2", rotation.rotation_start + timedelta(weeks=3), rotation.rotation_start + timedelta(weeks=4)),
        ("U1", rotation.rotation_start + timedelta(weeks=4), rotation.rotation_start + timedelta(weeks=5)),
        ("U2", rotation.rotation_start + timedelta(weeks=5), rotation.rotation_start + timedelta(weeks=6)),
        ("U1", rotation.rotation_start + timedelta(weeks=6), rotation.rotation_start + timedelta(weeks=7)),
        ("U2", rotation.rotation_start + timedelta(weeks=7), rotation.rotation_start + timedelta(weeks=8)),
        ("U1", rotation.rotation_start + timedelta(weeks=8), rotation.rotation_start + timedelta(weeks=9)),
        ("U2", rotation.rotation_start + timedelta(weeks=9), rotation.rotation_start + timedelta(weeks=10)),
        ("U1", rotation.rotation_start + timedelta(weeks=10), rotation.rotation_start + timedelta(weeks=11)),
        ("U2", rotation.rotation_start + timedelta(weeks=11), rotation.rotation_start + timedelta(weeks=12)),
        ("U1", rotation.rotation_start + timedelta(weeks=12), rotation.rotation_start + timedelta(weeks=13)),
    ]


@pytest.mark.unit
def test_get_rotation_shifts_returns_none_for_an_unknown_handle() -> None:
    assert UserRotationsService(rotations=[_rotation()]).get_rotation_shifts("unknown") is None
