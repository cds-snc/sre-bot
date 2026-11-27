"""Behavior tests for the Slack write handle.

Writes that are not idempotent (a posted message, a bookmark) must not be
replayed after a connection or server error, because Slack may already have
applied them; a rate-limited request was never processed, so it alone is
retried. The handle is a real ``AsyncWebClient`` built from environment
settings; the assertions read its retry handlers and token, and building it
is checked with outbound sockets disabled.
"""

import socket

import pytest
from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler
from slack_sdk.web.async_client import AsyncWebClient

from integrations.slack.client import get_async_slack_web_client, get_async_slack_write_client

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _slack_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", "T0TEST")
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-bot-token")
    monkeypatch.setenv("SLACK__REQUEST_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("SLACK__RETRY_MAX_ATTEMPTS", "4")


def test_write_handle_retries_only_rate_limited_requests() -> None:
    """The only retry handler is the rate-limit one, with the configured budget."""
    handlers = get_async_slack_write_client().retry_handlers

    assert len(handlers) == 1
    assert isinstance(handlers[0], AsyncRateLimitErrorRetryHandler)
    assert handlers[0].max_retry_count == 4


def test_write_handle_acts_as_the_bot_with_the_configured_timeout() -> None:
    client = get_async_slack_write_client()

    assert isinstance(client, AsyncWebClient)
    assert client.token == "xoxb-bot-token"
    assert client.timeout == 15


def test_building_the_write_handle_opens_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("building a client must not open a connection")

    monkeypatch.setattr(socket, "create_connection", _refuse)

    get_async_slack_write_client()


def test_a_caller_with_its_own_retry_point_overrides_timeout_and_rate_limit_retries() -> None:
    """A caller that owns durable retry builds a handle that never waits on a 429 in process."""
    client = get_async_slack_write_client(timeout_seconds=2, rate_limit_retries=0)

    assert client.timeout == 2
    assert client.retry_handlers == []


def test_the_read_client_takes_the_same_overrides() -> None:
    """A lookup bounded by a delivery deadline gets a short timeout and no retries."""
    client = get_async_slack_web_client(timeout_seconds=2, retries=0)

    assert client.timeout == 2
    assert client.retry_handlers == []


def test_the_defaults_are_unchanged_for_every_other_caller() -> None:
    """Without overrides the factories keep the configured timeout and retry budget."""
    reads = get_async_slack_web_client()

    assert reads.timeout == 15
    assert [handler.max_retry_count for handler in reads.retry_handlers] == [4, 4, 4]
