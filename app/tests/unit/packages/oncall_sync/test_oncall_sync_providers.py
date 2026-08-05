"""Unit tests for on-call sync provider wiring."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from integrations.slack.client import SlackClientManager
from integrations.slack.settings import get_slack_settings
from packages.oncall_sync import providers
from packages.oncall_sync.adapters.slack import SlackUserGroupTarget
from packages.oncall_sync.settings import OnCallRotation

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _provider_cache_isolation() -> Iterator[None]:
    providers.get_user_group_sync_target.cache_clear()
    get_slack_settings.cache_clear()
    SlackClientManager._client = None
    yield
    providers.get_user_group_sync_target.cache_clear()
    get_slack_settings.cache_clear()
    SlackClientManager._client = None


def _rotation() -> OnCallRotation:
    return OnCallRotation(
        opsgenie_schedule_id="abc",
        opsgenie_rotation_name="rot",
        slack_handle="oncall-x",
        slack_name="On-call X",
        slack_description="desc",
    )


def test_get_user_group_sync_target_builds_client_with_user_token() -> None:
    SlackClientManager._client = MagicMock(token="xoxb-shared-token")

    target = providers.get_user_group_sync_target()

    assert isinstance(target, SlackUserGroupTarget)
    assert target._client.token == "xoxp-user-token"


def test_usergroup_write_is_issued_via_user_scoped_client() -> None:
    SlackClientManager._client = MagicMock(token="xoxb-shared-token")

    target = providers.get_user_group_sync_target()
    target._client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    target._client.usergroups_list.return_value = {"usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 0}]}

    target.sync_user_group(_rotation(), "a@x.ca")

    target._client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")
    assert target._client.token == "xoxp-user-token"


def test_get_user_group_sync_target_raises_when_user_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-shared-token")
    monkeypatch.delenv("SLACK_USER_TOKEN", raising=False)

    with pytest.raises(ValueError, match="SLACK_USER_TOKEN"):
        providers.get_user_group_sync_target()
