"""Unit tests for the Slack user-group sync target adapter."""

from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from packages.oncall_sync.adapters.slack import SlackUserGroupTarget
from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation


def _rotation() -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id="abc",
        opsgenie_rotation_name="rot",
        slack_handle="oncall-x",
        slack_name="On-call X",
        slack_description="desc",
    )


def _slack_error(code: str) -> SlackApiError:
    response = MagicMock()
    response.get = lambda key, default=None: {"error": code}.get(key, default)
    return SlackApiError("err", response)


@pytest.mark.unit
def test_updates_existing_user_group() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {
        "usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 0}]
    }

    SlackUserGroupTarget(client).sync_user_group(_rotation(), "a@x.ca")

    client.usergroups_create.assert_not_called()
    client.usergroups_enable.assert_not_called()
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
def test_creates_user_group_when_missing() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": []}
    client.usergroups_create.return_value = {"usergroup": {"id": "S999"}}

    SlackUserGroupTarget(client).sync_user_group(_rotation(), "a@x.ca")

    client.usergroups_create.assert_called_once_with(
        name="On-call X", handle="oncall-x", description="desc"
    )
    client.usergroups_users_update.assert_called_once_with(usergroup="S999", users="U1")


@pytest.mark.unit
def test_reenables_disabled_user_group() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {
        "usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 123456}]
    }

    SlackUserGroupTarget(client).sync_user_group(_rotation(), "a@x.ca")

    client.usergroups_enable.assert_called_once_with(usergroup="S123")
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
def test_skips_when_email_does_not_resolve_to_slack_user() -> None:
    client = MagicMock()
    client.users_lookupByEmail.side_effect = _slack_error("users_not_found")

    SlackUserGroupTarget(client).sync_user_group(_rotation(), "missing@x.ca")

    client.usergroups_list.assert_not_called()
    client.usergroups_create.assert_not_called()
    client.usergroups_users_update.assert_not_called()


@pytest.mark.unit
def test_wraps_slack_api_error_in_oncall_sync_error() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": []}
    client.usergroups_create.side_effect = _slack_error("invalid_handle")

    with pytest.raises(OnCallSyncError) as excinfo:
        SlackUserGroupTarget(client).sync_user_group(_rotation(), "a@x.ca")

    assert isinstance(excinfo.value.__cause__, SlackApiError)
