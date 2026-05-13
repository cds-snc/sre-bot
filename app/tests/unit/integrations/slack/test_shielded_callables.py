"""Tests for `ShieldedSay` and `ShieldedRespond`.

Verifies that both shielded callables:
- Preserve Bolt's native call signatures
- Route through the correct shield executor path
- Return `OperationResult` (never raise `SlackApiError`)
- Handle missing `response_url` gracefully for `ShieldedRespond`
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings
from integrations.slack.shield import ShieldedRespond, ShieldedSay, SlackShield

pytestmark = pytest.mark.unit


@pytest.fixture
def shield() -> SlackShield:
    return SlackShield(settings=SlackSettings(SLACK_BOT_TOKEN="xoxb-test"))


class TestShieldedSay:
    """`ShieldedSay` routes through `execute_say` and returns `OperationResult`."""

    async def test_call_returns_operation_result(self, shield: SlackShield) -> None:
        say = ShieldedSay(shield=shield, channel="C123")

        with patch.object(
            shield.web,
            "chat_postMessage",
            return_value={"ok": True, "ts": "12345.67"},
        ):
            result = await say(text="hello")

        assert isinstance(result, OperationResult)
        assert result.is_success

    async def test_channel_is_forwarded_to_chat_post_message(
        self, shield: SlackShield
    ) -> None:
        say = ShieldedSay(shield=shield, channel="C_TARGET")
        captured: dict[str, Any] = {}

        async def mock_post(**kwargs: Any):
            captured.update(kwargs)
            return {"ok": True}

        with patch.object(shield.web, "chat_postMessage", side_effect=mock_post):
            await say(text="hi")

        assert captured["channel"] == "C_TARGET"

    async def test_thread_ts_from_constructor_is_forwarded(
        self, shield: SlackShield
    ) -> None:
        say = ShieldedSay(shield=shield, channel="C123", thread_ts="111.222")
        captured: dict[str, Any] = {}

        async def mock_post(**kwargs: Any):
            captured.update(kwargs)
            return {"ok": True}

        with patch.object(shield.web, "chat_postMessage", side_effect=mock_post):
            await say(text="hi")

        assert captured["thread_ts"] == "111.222"

    async def test_explicit_thread_ts_overrides_constructor_value(
        self, shield: SlackShield
    ) -> None:
        say = ShieldedSay(shield=shield, channel="C123", thread_ts="old.ts")
        captured: dict[str, Any] = {}

        async def mock_post(**kwargs: Any):
            captured.update(kwargs)
            return {"ok": True}

        with patch.object(shield.web, "chat_postMessage", side_effect=mock_post):
            await say(text="hi", thread_ts="new.ts")

        assert captured["thread_ts"] == "new.ts"

    async def test_slack_api_error_is_classified_not_raised(
        self, shield: SlackShield
    ) -> None:
        from slack_sdk.errors import SlackApiError

        response = MagicMock()
        response.data = {"ok": False, "error": "channel_not_found"}
        response.headers = {}

        async def mock_post(**kwargs: Any):
            raise SlackApiError("channel_not_found", response=response)

        with patch.object(shield.web, "chat_postMessage", side_effect=mock_post):
            say = ShieldedSay(shield=shield, channel="C_MISSING")
            result = await say(text="hi")

        assert result.status == OperationStatus.NOT_FOUND


class TestShieldedRespond:
    """`ShieldedRespond` routes through `execute_respond` and returns `OperationResult`."""

    async def test_call_returns_operation_result(self, shield: SlackShield) -> None:
        webhook_response = MagicMock()
        webhook_response.status_code = 200
        webhook_response.headers = {}

        respond = ShieldedRespond(shield=shield, response_url="https://hooks.slack.com/x")

        with patch.object(respond._client, "send", return_value=webhook_response):
            result = await respond(text="hello")

        assert isinstance(result, OperationResult)
        assert result.is_success

    async def test_missing_response_url_returns_permanent_error(
        self, shield: SlackShield
    ) -> None:
        respond = ShieldedRespond(shield=shield, response_url=None)

        result = await respond(text="hello")

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "missing_response_url"

    async def test_http_404_classifies_as_permanent_error(
        self, shield: SlackShield
    ) -> None:
        webhook_response = MagicMock()
        webhook_response.status_code = 404
        webhook_response.headers = {}

        respond = ShieldedRespond(
            shield=shield, response_url="https://hooks.slack.com/expired"
        )

        with patch.object(respond._client, "send", return_value=webhook_response):
            result = await respond(text="too late")

        assert result.status == OperationStatus.PERMANENT_ERROR

    async def test_replace_original_is_forwarded(self, shield: SlackShield) -> None:
        webhook_response = MagicMock()
        webhook_response.status_code = 200
        webhook_response.headers = {}
        captured: dict[str, Any] = {}

        async def mock_send(**kwargs: Any):
            captured.update(kwargs)
            return webhook_response

        respond = ShieldedRespond(
            shield=shield, response_url="https://hooks.slack.com/x"
        )

        with patch.object(respond._client, "send", side_effect=mock_send):
            await respond(text="updated", replace_original=True)

        assert captured.get("replace_original") is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _coroutine(value: Any) -> Any:
    return value
