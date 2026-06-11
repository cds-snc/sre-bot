"""Unit tests for the slack_opsgenie_sync sync routine."""

from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from infrastructure.configuration.features.slack_opsgenie_sync import OnCallRotation
from integrations.opsgenie import OpsGenieAPIError
from modules.slack_opsgenie_sync import sync as sync_module
from modules.slack_opsgenie_sync.sync import RotationSyncError


def _rotation(
    handle: str = "oncall-x",
    schedule_id: str = "abc-123",
    rotation_name: str = "rot",
) -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id=schedule_id,
        opsgenie_rotation_name=rotation_name,
        slack_handle=handle,
        slack_name="On-call X",
        slack_description="desc",
    )


def _slack_error(code: str) -> SlackApiError:
    response = MagicMock()
    response.get = lambda key, default=None: {"error": code}.get(key, default)
    return SlackApiError("err", response)


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_updates_existing_group(mock_get_on_call) -> None:
    mock_get_on_call.return_value = "a@x.ca"
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {
        "usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 0}]
    }

    sync_module._sync_rotation(client, _rotation())

    client.usergroups_create.assert_not_called()
    client.usergroups_enable.assert_not_called()
    client.usergroups_disable.assert_not_called()
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_creates_group_when_missing(mock_get_on_call) -> None:
    mock_get_on_call.return_value = "a@x.ca"
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": []}
    client.usergroups_create.return_value = {"usergroup": {"id": "S999"}}

    sync_module._sync_rotation(client, _rotation())

    client.usergroups_create.assert_called_once_with(
        name="On-call X", handle="oncall-x", description="desc"
    )
    client.usergroups_users_update.assert_called_once_with(usergroup="S999", users="U1")


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_enables_disabled_group(mock_get_on_call) -> None:
    mock_get_on_call.return_value = "a@x.ca"
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {
        "usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 123456}]
    }

    sync_module._sync_rotation(client, _rotation())

    client.usergroups_enable.assert_called_once_with(usergroup="S123")
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_leaves_group_untouched_when_rotation_empty(
    mock_get_on_call,
) -> None:
    mock_get_on_call.return_value = None
    client = MagicMock()

    sync_module._sync_rotation(client, _rotation())

    client.usergroups_disable.assert_not_called()
    client.usergroups_users_update.assert_not_called()
    client.usergroups_list.assert_not_called()
    client.usergroups_create.assert_not_called()
    client.users_lookupByEmail.assert_not_called()


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_wraps_opsgenie_errors_in_rotation_sync_error(
    mock_get_on_call,
) -> None:
    mock_get_on_call.side_effect = OpsGenieAPIError("boom")
    client = MagicMock()

    with pytest.raises(RotationSyncError) as excinfo:
        sync_module._sync_rotation(client, _rotation())

    assert isinstance(excinfo.value.__cause__, OpsGenieAPIError)


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_wraps_slack_errors_in_rotation_sync_error(
    mock_get_on_call,
) -> None:
    mock_get_on_call.return_value = "a@x.ca"
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": []}
    client.usergroups_create.side_effect = _slack_error("invalid_handle")

    with pytest.raises(RotationSyncError) as excinfo:
        sync_module._sync_rotation(client, _rotation())

    assert isinstance(excinfo.value.__cause__, SlackApiError)


@pytest.mark.unit
@patch.object(sync_module, "get_on_call_user_for_rotation")
def test_sync_rotation_leaves_group_unchanged_when_slack_lookup_fails(
    mock_get_on_call,
) -> None:
    mock_get_on_call.return_value = "missing@x.ca"
    client = MagicMock()
    client.users_lookupByEmail.side_effect = _slack_error("users_not_found")

    sync_module._sync_rotation(client, _rotation())

    client.usergroups_list.assert_not_called()
    client.usergroups_users_update.assert_not_called()
    client.usergroups_disable.assert_not_called()


@pytest.mark.unit
@patch.object(sync_module, "SlackClientManager")
@patch.object(sync_module, "get_slack_opsgenie_sync_settings")
def test_sync_all_rotations_isolates_per_rotation_failures(
    mock_get_settings, mock_client_mgr
) -> None:
    settings = MagicMock()
    settings.rotations = [_rotation("a"), _rotation("b")]
    mock_get_settings.return_value = settings

    client = MagicMock()
    mock_client_mgr.get_client.return_value = client

    with patch.object(sync_module, "_sync_rotation") as mock_sync:
        mock_sync.side_effect = [RotationSyncError("boom"), None]
        sync_module.sync_all_rotations()

    assert mock_sync.call_count == 2
