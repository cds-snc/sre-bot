"""Behavior tests for the Slack Web client factories.

Each factory returns a real slack_sdk client whose token, per-call timeout
and SDK-native retry handlers come from ``integrations.slack.settings``.
Settings are supplied through environment variables; the autouse provider
cache clear makes each test observe its own values. Construction is checked
with outbound sockets disabled to prove building a client performs no I/O.
"""

import socket

import pytest
from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncConnectionErrorRetryHandler,
    AsyncRateLimitErrorRetryHandler,
    AsyncServerErrorRetryHandler,
)
from slack_sdk.http_retry.builtin_handlers import (
    ConnectionErrorRetryHandler,
    RateLimitErrorRetryHandler,
    ServerErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient

from integrations.slack.client import get_async_slack_web_client, get_slack_web_client

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _slack_transport_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-bot-token")
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-user-token")
    monkeypatch.setenv("SLACK_REQUEST_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("SLACK_RETRY_MAX_ATTEMPTS", "4")


class TestSyncFactory:
    def test_default_client_uses_the_bot_token_and_timeout(self) -> None:
        client = get_slack_web_client()

        assert isinstance(client, WebClient)
        assert client.token == "xoxb-bot-token"
        assert client.timeout == 15

    def test_user_actor_uses_the_user_token(self) -> None:
        assert get_slack_web_client(actor="user").token == "xoxp-user-token"

    def test_sdk_retry_handlers_carry_the_configured_budget(self) -> None:
        handlers = get_slack_web_client().retry_handlers

        assert [type(handler) for handler in handlers] == [
            ConnectionErrorRetryHandler,
            RateLimitErrorRetryHandler,
            ServerErrorRetryHandler,
        ]
        assert {handler.max_retry_count for handler in handlers} == {4}

    def test_each_call_builds_a_new_client(self) -> None:
        assert get_slack_web_client() is not get_slack_web_client()


class TestAsyncFactory:
    def test_client_uses_the_bot_token_and_timeout(self) -> None:
        client = get_async_slack_web_client()

        assert isinstance(client, AsyncWebClient)
        assert client.token == "xoxb-bot-token"
        assert client.timeout == 15

    def test_sdk_retry_handlers_carry_the_configured_budget(self) -> None:
        handlers = get_async_slack_web_client().retry_handlers

        assert [type(handler) for handler in handlers] == [
            AsyncConnectionErrorRetryHandler,
            AsyncRateLimitErrorRetryHandler,
            AsyncServerErrorRetryHandler,
        ]
        assert {handler.max_retry_count for handler in handlers} == {4}


def test_building_clients_opens_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("client construction must not open a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    get_slack_web_client()
    get_slack_web_client(actor="user")
    get_async_slack_web_client()
