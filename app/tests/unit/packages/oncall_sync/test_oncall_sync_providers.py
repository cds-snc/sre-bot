"""Unit tests for on-call sync provider wiring."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from packages.oncall_sync import providers
from packages.oncall_sync.adapters.slack import SlackUserGroupTarget

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _provider_cache_isolation() -> Iterator[None]:
    providers.get_user_group_sync_target.cache_clear()
    yield
    providers.get_user_group_sync_target.cache_clear()


def test_get_user_group_sync_target_builds_client_with_user_token(monkeypatch: pytest.MonkeyPatch) -> None:
    web_client = MagicMock(token="xoxp-user-token")
    web_client_ctor = MagicMock(return_value=web_client)
    monkeypatch.setattr(providers, "get_slack_settings", lambda: SimpleNamespace(USER_TOKEN="xoxp-user-token"))
    monkeypatch.setattr(providers, "WebClient", web_client_ctor)

    target = providers.get_user_group_sync_target()

    assert isinstance(target, SlackUserGroupTarget)
    assert target._client is web_client
    web_client_ctor.assert_called_once_with(token="xoxp-user-token")


def test_usergroup_write_is_issued_via_user_scoped_client(monkeypatch: pytest.MonkeyPatch) -> None:
    web_client = MagicMock(token="xoxp-user-token")
    monkeypatch.setattr(providers, "get_slack_settings", lambda: SimpleNamespace(USER_TOKEN="xoxp-user-token"))
    monkeypatch.setattr(providers, "WebClient", MagicMock(return_value=web_client))

    target = providers.get_user_group_sync_target()
    web_client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": "U1"}}
    web_client.usergroups_list.return_value = {"usergroups": [{"id": "S123", "handle": "oncall-x", "date_delete": 0}]}

    target.sync_user_group("oncall-x", "On-call X", "desc", ["a@x.ca"])

    web_client.usergroups_users_update.assert_called_once_with(usergroup="S123", users="U1")
    assert target._client.token == "xoxp-user-token"


def test_get_user_group_sync_target_raises_when_user_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(providers, "get_slack_settings", lambda: SimpleNamespace(USER_TOKEN=""))

    with pytest.raises(ValueError, match="SLACK_USER_TOKEN"):
        providers.get_user_group_sync_target()


def test_get_user_group_sync_target_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    web_client = MagicMock(token="xoxp-user-token")
    web_client_ctor = MagicMock(return_value=web_client)
    monkeypatch.setattr(providers, "get_slack_settings", lambda: SimpleNamespace(USER_TOKEN="xoxp-user-token"))
    monkeypatch.setattr(providers, "WebClient", web_client_ctor)

    first = providers.get_user_group_sync_target()
    second = providers.get_user_group_sync_target()

    assert first is second
    web_client_ctor.assert_called_once_with(token="xoxp-user-token")
