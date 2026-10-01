"""Unit tests for the rant Slack user-identity lookup adapter."""

from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from packages.rant.adapters import slack as slack_adapter
from packages.rant.adapters.slack import SlackUserIdentityLookup, build_user_identity_lookup
from packages.rant.service import UserIdentity, UserIdentityLookup

pytestmark = pytest.mark.unit


def _client(profile: dict[str, str]) -> MagicMock:
    """Stub Web client whose ``users_info`` answers with the given profile."""
    client = MagicMock()
    client.users_info.return_value = {"ok": True, "user": {"profile": profile}}
    return client


def test_lookup_calls_users_info_and_returns_name_and_avatar() -> None:
    """One ``users.info`` call for the user yields their display name and largest avatar."""
    client = _client({"display_name": "Ada", "real_name": "Ada Lovelace", "image_512": "https://img/512.png"})

    identity = SlackUserIdentityLookup(client).lookup_user_identity("U123")

    client.users_info.assert_called_once_with(user="U123")
    assert identity == UserIdentity(display_name="Ada", icon_url="https://img/512.png")


def test_lookup_falls_back_to_real_name_and_smaller_avatars() -> None:
    """A blank display name and a missing 512px avatar fall back to the next best values."""
    client = _client({"display_name": "", "real_name": "Ada Lovelace", "image_72": "https://img/72.png"})

    identity = SlackUserIdentityLookup(client).lookup_user_identity("U123")

    assert identity == UserIdentity(display_name="Ada Lovelace", icon_url="https://img/72.png")


def test_lookup_returns_none_when_response_is_not_ok() -> None:
    """A not-ok answer carries no usable identity."""
    client = MagicMock()
    client.users_info.return_value = {"ok": False, "error": "user_not_found"}

    assert SlackUserIdentityLookup(client).lookup_user_identity("U123") is None


@pytest.mark.parametrize("profile", [{"display_name": "Ada"}, {"image_512": "https://img/512.png"}, {}])
def test_lookup_returns_none_when_profile_is_incomplete(profile: dict[str, str]) -> None:
    """Posting as the user needs both a name and an avatar; either one missing yields nothing."""
    assert SlackUserIdentityLookup(_client(profile)).lookup_user_identity("U123") is None


def test_lookup_propagates_slack_api_errors() -> None:
    """The adapter does not swallow Web API errors; the handler owns the fallback."""
    client = MagicMock()
    client.users_info.side_effect = SlackApiError("err", {"ok": False, "error": "ratelimited"})

    with pytest.raises(SlackApiError):
        SlackUserIdentityLookup(client).lookup_user_identity("U123")


def test_build_user_identity_lookup_uses_the_bot_web_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The built adapter satisfies the package Protocol and calls through the shared client factory's client."""
    client = _client({"display_name": "Ada", "image_512": "https://img/512.png"})
    monkeypatch.setattr(slack_adapter, "get_slack_web_client", lambda: client)

    lookup = build_user_identity_lookup()

    assert isinstance(lookup, UserIdentityLookup)
    lookup.lookup_user_identity("U123")
    client.users_info.assert_called_once_with(user="U123")
