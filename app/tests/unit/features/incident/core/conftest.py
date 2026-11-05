"""Shared fixtures for the incident core unit tests."""

from collections.abc import Callable, Sequence
from typing import Any
from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient


def slack_error(code: str) -> SlackApiError:
    """Return a ``SlackApiError`` carrying ``code`` as Slack's error field."""
    return SlackApiError(f"The request to the Slack API failed. (error: {code})", {"ok": False, "error": code})


class StubSlack:
    """Read and write Web clients over a few channels, answering as the Slack Web API does.

    ``channels`` maps a channel id to its ``is_archived`` and ``is_member`` flags; any
    other id is ``channel_not_found``. Writes to an archived channel answer
    ``is_archived`` and writes where the bot is no member ``not_in_channel``;
    ``fail_with`` makes every call raise that Slack code instead. Posted messages get
    ``ts`` values ``1700000000.00000<n>``.
    """

    def __init__(self, channels: dict[str, dict[str, bool]] | None = None, *, fail_with: str | None = None) -> None:
        self.channels = channels if channels is not None else {"C0OPEN": {"is_archived": False, "is_member": True}}
        self.fail_with = fail_with
        self.reads = AsyncMock(spec=AsyncWebClient)
        self.writes = AsyncMock(spec=AsyncWebClient)
        self.reads.conversations_info.side_effect = self._info
        self.writes.chat_postMessage.side_effect = self._post
        self.writes.conversations_setPurpose.side_effect = self._channel_write("channel")
        self.writes.bookmarks_add.side_effect = self._channel_write("channel_id")
        self.writes.conversations_invite.side_effect = self._invite
        self.writes.conversations_archive.side_effect = self._archive
        self._posted = 0

    error = staticmethod(slack_error)

    def _check(self, channel: str) -> dict[str, bool]:
        if self.fail_with:
            raise slack_error(self.fail_with)
        if channel not in self.channels:
            raise slack_error("channel_not_found")
        return self.channels[channel]

    def _writable(self, channel: str) -> None:
        state = self._check(channel)
        if state["is_archived"]:
            raise slack_error("is_archived")
        if not state["is_member"]:
            raise slack_error("not_in_channel")

    async def _info(self, *, channel: str, **_: Any) -> dict[str, Any]:
        state = self._check(channel)
        return {"ok": True, "channel": {"id": channel, **state}}

    async def _post(self, *, channel: str, text: str, **_: Any) -> dict[str, Any]:
        self._writable(channel)
        self._posted += 1
        return {"ok": True, "channel": channel, "ts": f"1700000000.{self._posted:06d}"}

    def _channel_write(self, key: str) -> Callable[..., Any]:
        async def _write(**kwargs: Any) -> dict[str, Any]:
            self._writable(kwargs[key])
            return {"ok": True}

        return _write

    async def _invite(self, *, channel: str, users: Sequence[str] | str, **_: Any) -> dict[str, Any]:
        self._writable(channel)
        return {"ok": True}

    async def _archive(self, *, channel: str, **_: Any) -> dict[str, Any]:
        state = self._check(channel)
        if state["is_archived"]:
            raise slack_error("already_archived")
        if not state["is_member"]:
            raise slack_error("not_in_channel")
        state["is_archived"] = True
        return {"ok": True}


@pytest.fixture
def stub_slack() -> Callable[..., StubSlack]:
    """Return the ``StubSlack`` constructor."""
    return StubSlack
