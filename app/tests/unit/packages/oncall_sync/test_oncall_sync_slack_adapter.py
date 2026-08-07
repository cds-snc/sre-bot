"""Unit tests for the Slack user-group sync target adapter."""

from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from packages.oncall_sync.adapters.slack import SlackUserGroupTarget
from packages.oncall_sync.ports import OnCallSyncError


def _slack_error(code: str) -> SlackApiError:
    response = MagicMock()
    response.get = lambda key, default=None: {"error": code}.get(key, default)
    return SlackApiError("err", response)


def _sync(client, emails: list[str], *, handle: str = "oncall-x", name: str = "On-call X", description: str = "desc") -> None:
    SlackUserGroupTarget(client).sync_user_group(handle, name, description, emails)


# ---------------------------------------------------------------------------
# Single-email (rotation group) behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_updates_existing_user_group() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 0}]}

    _sync(client, ["a@x.ca"])

    client.usergroups_create.assert_not_called()
    client.usergroups_enable.assert_not_called()
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
def test_creates_user_group_when_missing() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": []}
    client.usergroups_create.return_value = {"usergroup": {"id": "S999"}}

    _sync(client, ["a@x.ca"])

    client.usergroups_create.assert_called_once_with(name="On-call X", handle="oncall-x", description="desc")
    client.usergroups_users_update.assert_called_once_with(usergroup="S999", users="U1")


@pytest.mark.unit
def test_reenables_disabled_user_group() -> None:
    client = MagicMock()
    client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    client.usergroups_list.return_value = {"usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 123456}]}

    _sync(client, ["a@x.ca"])

    client.usergroups_enable.assert_called_once_with(usergroup="S123")
    client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")


@pytest.mark.unit
def test_skips_when_email_does_not_resolve_to_user() -> None:
    client = MagicMock()
    client.users_lookupByEmail.side_effect = _slack_error("users_not_found")

    _sync(client, ["missing@x.ca"])

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
        _sync(client, ["a@x.ca"])

    assert isinstance(excinfo.value.__cause__, SlackApiError)


# ---------------------------------------------------------------------------
# Multi-email (schedule aggregate group) behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sets_all_resolved_users_for_multi_email() -> None:
    client = MagicMock()
    client.users_lookupByEmail.side_effect = [
        {"ok": True, "user": {"id": "U1"}},
        {"ok": True, "user": {"id": "U2"}},
    ]
    client.usergroups_list.return_value = {"usergroups": [{"id": "S1", "handle": "oncall-x", "date_delete": 0}]}

    _sync(client, ["a@x.ca", "b@x.ca"])

    client.usergroups_users_update.assert_called_once_with(usergroup="S1", users="U1,U2")


@pytest.mark.unit
def test_skips_unresolvable_emails_in_multi_email() -> None:
    client = MagicMock()
    client.users_lookupByEmail.side_effect = [
        {"ok": True, "user": {"id": "U1"}},
        _slack_error("users_not_found"),
    ]
    client.usergroups_list.return_value = {"usergroups": [{"id": "S1", "handle": "oncall-x", "date_delete": 0}]}

    _sync(client, ["a@x.ca", "missing@x.ca"])

    client.usergroups_users_update.assert_called_once_with(usergroup="S1", users="U1")


@pytest.mark.unit
def test_skips_update_when_no_emails_resolve() -> None:
    client = MagicMock()
    client.users_lookupByEmail.side_effect = _slack_error("users_not_found")

    _sync(client, ["missing@x.ca"])

    client.usergroups_list.assert_not_called()
    client.usergroups_users_update.assert_not_called()
