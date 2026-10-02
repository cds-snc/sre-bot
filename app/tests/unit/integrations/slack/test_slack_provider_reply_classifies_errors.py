"""Behavior tests for the reply interface exposed by ``SlackPlatformProvider.reply``.

The provider's Web client is replaced by a recording stub, so each test
observes the exact Web API call a reply method issues and the
``OperationResult`` it returns. Failures are real ``SlackApiError`` objects
carrying real ``SlackResponse`` payloads and headers, as slack_sdk raises
them: the interface must classify them into a result and never raise, because
handlers branch on the result instead of catching SDK exceptions.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from contracts.operations import OperationStatus
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


def _slack_error(code: str, *, headers: dict[str, str] | None = None, status_code: int = 200) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/chat.postMessage",
        req_args={},
        data={"ok": False, "error": code},
        headers=headers or {},
        status_code=status_code,
    )
    return SlackApiError(f"The request to the Slack API failed. (error: {code})", response)


def _provider(client: Any | None) -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(settings=settings)
    provider._client = client
    return provider


def test_provider_is_a_registrar_whose_reply_is_a_reply_sender() -> None:
    registrar: SlackCommandRegistrar = _provider(MagicMock())
    reply: SlackReplySender = registrar.reply

    assert reply is registrar.reply


class TestWebApiCalls:
    """Each reply method issues one Web API call and reports success."""

    def test_post_message_sends_customized_chat_post_message(self) -> None:
        client = MagicMock()

        result = _provider(client).reply.post_message(channel_id="C1", text="*HI*", username="Ada", icon_url="https://img/a.png")

        client.chat_postMessage.assert_called_once_with(channel="C1", text="*HI*", username="Ada", icon_url="https://img/a.png")
        assert result.status is OperationStatus.SUCCESS

    def test_post_message_without_customization_passes_none(self) -> None:
        client = MagicMock()

        _provider(client).reply.post_message(channel_id="C1", text="hi")

        client.chat_postMessage.assert_called_once_with(channel="C1", text="hi", username=None, icon_url=None)

    def test_post_ephemeral_targets_the_user_in_the_channel(self) -> None:
        client = MagicMock()

        result = _provider(client).reply.post_ephemeral(channel_id="C1", user_id="U1", text="working")

        client.chat_postEphemeral.assert_called_once_with(channel="C1", user="U1", text="working")
        assert result.status is OperationStatus.SUCCESS

    def test_open_view_passes_the_trigger_and_view(self) -> None:
        client = MagicMock()
        view = {"type": "modal"}

        result = _provider(client).reply.open_view(trigger_id="T1", view=view)

        client.views_open.assert_called_once_with(trigger_id="T1", view=view)
        assert result.status is OperationStatus.SUCCESS


class TestFailuresAreClassifiedNotRaised:
    """Web API failures come back as error results."""

    def test_rate_limit_is_transient_with_the_retry_after_hint(self) -> None:
        client = MagicMock()
        client.chat_postMessage.side_effect = _slack_error("ratelimited", headers={"Retry-After": "7"}, status_code=429)

        result = _provider(client).reply.post_message(channel_id="C1", text="hi")

        assert result.status is OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ratelimited"
        assert result.retry_after == 7

    def test_missing_scope_is_unauthorized(self) -> None:
        client = MagicMock()
        client.chat_postEphemeral.side_effect = _slack_error("missing_scope")

        result = _provider(client).reply.post_ephemeral(channel_id="C1", user_id="U1", text="hi")

        assert result.status is OperationStatus.UNAUTHORIZED
        assert result.error_code == "missing_scope"

    def test_unmapped_slack_code_is_a_permanent_error_carrying_the_code(self) -> None:
        client = MagicMock()
        error = _slack_error("expired_trigger_id")
        client.views_open.side_effect = error

        result = _provider(client).reply.open_view(trigger_id="T1", view={})

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "expired_trigger_id"
        assert result.cause is error

    def test_non_slack_exception_is_a_permanent_error(self) -> None:
        client = MagicMock()
        error = RuntimeError("connection reset")
        client.chat_postMessage.side_effect = error

        result = _provider(client).reply.post_message(channel_id="C1", text="hi")

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "UNEXPECTED_ERROR"
        assert result.cause is error

    def test_reply_before_the_provider_starts_is_an_error_result(self) -> None:
        result = _provider(None).reply.post_message(channel_id="C1", text="hi")

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == "INITIALIZATION_ERROR"
