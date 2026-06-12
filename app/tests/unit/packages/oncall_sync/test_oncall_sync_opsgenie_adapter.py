"""Unit tests for the OpsGenie on-call schedule adapter."""

from unittest.mock import patch

import pytest

from integrations.opsgenie import OpsGenieAPIError
from packages.oncall_sync.adapters.opsgenie import OpsGenieScheduleProvider
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation


def _rotation() -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id="sched-1",
        opsgenie_rotation_name="rot-1",
        slack_handle="oncall-x",
        slack_name="On-call X",
    )


@pytest.mark.unit
@patch("packages.oncall_sync.adapters.opsgenie.get_on_call_user_for_rotation")
def test_returns_email_from_underlying_client(mock_get) -> None:
    mock_get.return_value = "a@x.ca"

    result = OpsGenieScheduleProvider().get_current_on_call_email(_rotation())

    assert result == "a@x.ca"
    mock_get.assert_called_once_with("sched-1", "rot-1")


@pytest.mark.unit
@patch("packages.oncall_sync.adapters.opsgenie.get_on_call_user_for_rotation")
def test_returns_none_when_underlying_client_returns_none(mock_get) -> None:
    mock_get.return_value = None

    assert OpsGenieScheduleProvider().get_current_on_call_email(_rotation()) is None


@pytest.mark.unit
@patch("packages.oncall_sync.adapters.opsgenie.get_on_call_user_for_rotation")
def test_wraps_opsgenie_api_error_in_oncall_sync_error(mock_get) -> None:
    mock_get.side_effect = OpsGenieAPIError("boom")

    with pytest.raises(OnCallSyncError) as excinfo:
        OpsGenieScheduleProvider().get_current_on_call_email(_rotation())

    assert isinstance(excinfo.value.__cause__, OpsGenieAPIError)
