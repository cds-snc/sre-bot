"""Unit tests for SlackOpsGenieSyncSettings parsing and validation."""

import pytest

from infrastructure.configuration.features.slack_opsgenie_sync import (
    SlackOpsGenieSyncSettings,
)


@pytest.mark.unit
def test_defaults_when_no_env() -> None:
    settings = SlackOpsGenieSyncSettings()
    assert settings.rotations == []


@pytest.mark.unit
def test_parses_rotations_from_json_string() -> None:
    settings = SlackOpsGenieSyncSettings(
        SLACK_OPSGENIE_SYNC_ROTATIONS=(
            '[{"opsgenie_schedule_id": "abc", '
            '"opsgenie_rotation_name": "rot", '
            '"slack_handle": "oncall-x", '
            '"slack_name": "On-call X"}]'
        )
    )
    assert len(settings.rotations) == 1
    assert settings.rotations[0].slack_handle == "oncall-x"
    assert settings.rotations[0].opsgenie_rotation_name == "rot"
    assert settings.rotations[0].slack_description == "Auto-synced from OpsGenie"


@pytest.mark.unit
def test_accepts_rotations_as_list() -> None:
    settings = SlackOpsGenieSyncSettings(
        SLACK_OPSGENIE_SYNC_ROTATIONS=[
            {
                "opsgenie_schedule_id": "abc",
                "opsgenie_rotation_name": "rot",
                "slack_handle": "oncall-x",
                "slack_name": "On-call X",
            }
        ]
    )
    assert settings.rotations[0].opsgenie_schedule_id == "abc"
    assert settings.rotations[0].opsgenie_rotation_name == "rot"


@pytest.mark.unit
def test_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="Invalid SLACK_OPSGENIE_SYNC_ROTATIONS JSON"):
        SlackOpsGenieSyncSettings(SLACK_OPSGENIE_SYNC_ROTATIONS="{not json")


@pytest.mark.unit
def test_duplicate_handles_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate slack_handle"):
        SlackOpsGenieSyncSettings(
            SLACK_OPSGENIE_SYNC_ROTATIONS=[
                {
                    "opsgenie_schedule_id": "a",
                    "opsgenie_rotation_name": "rot1",
                    "slack_handle": "oncall-x",
                    "slack_name": "X",
                },
                {
                    "opsgenie_schedule_id": "b",
                    "opsgenie_rotation_name": "rot2",
                    "slack_handle": "oncall-x",
                    "slack_name": "Y",
                },
            ]
        )
