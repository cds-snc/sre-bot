"""Slack vendor client.

Provides the Slack Web client factories and the shared error classification
per decisions/outbound-clients.md: clients raise typed SDK exceptions
(``SlackApiError``); adapters classify them. Every client carries slack_sdk's
native connection, rate-limit and server-error retry handlers and the
per-call timeout, fixed once at construction; nothing else retries.

Clients are built per call and never cached here. slack_sdk clients hold no
connection until a request is made, so building one is cheap; a caller that
wants one shared instance caches the factory call in its own provider (as
``packages/oncall_sync/providers.py`` does).
"""

from typing import Literal

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
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

from contracts.operations.status import OperationStatus
from integrations.slack.settings import get_slack_settings

type SlackActor = Literal["bot", "user"]


def get_slack_web_client(*, actor: SlackActor = "bot") -> WebClient:
    """Build a sync Web client acting as the bot, or as the admin user whose token it holds."""
    settings = get_slack_settings()
    retries = settings.RETRY_MAX_ATTEMPTS
    return WebClient(
        token=settings.USER_TOKEN if actor == "user" else settings.BOT_TOKEN,
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
        retry_handlers=[
            ConnectionErrorRetryHandler(max_retry_count=retries),
            RateLimitErrorRetryHandler(max_retry_count=retries),
            ServerErrorRetryHandler(max_retry_count=retries),
        ],
    )


def get_async_slack_web_client() -> AsyncWebClient:
    """Build an async Web client for the bot token."""
    settings = get_slack_settings()
    retries = settings.RETRY_MAX_ATTEMPTS
    return AsyncWebClient(
        token=settings.BOT_TOKEN,
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
        retry_handlers=[
            AsyncConnectionErrorRetryHandler(max_retry_count=retries),
            AsyncRateLimitErrorRetryHandler(max_retry_count=retries),
            AsyncServerErrorRetryHandler(max_retry_count=retries),
        ],
    )


def classify_slack_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected Slack Web API errors; propagate unknown exceptions unchanged."""
    if not isinstance(exc, SlackApiError):
        raise exc

    code = exc.response.get("error")
    if not isinstance(code, str) or not code:
        raise exc

    settings = get_slack_settings()
    if code in settings.UNAUTHORIZED_ERRORS:
        return OperationStatus.UNAUTHORIZED, code, None
    if code in settings.NOT_FOUND_ERRORS:
        return OperationStatus.NOT_FOUND, code, None
    if code in settings.TRANSIENT_ERRORS:
        retry_after = _retry_after_seconds(exc)
        return (
            OperationStatus.TRANSIENT_ERROR,
            code,
            settings.TRANSIENT_RETRY_AFTER_SECONDS if retry_after is None else retry_after,
        )

    raise exc


def _retry_after_seconds(exc: SlackApiError) -> int | None:
    """Seconds from Slack's Retry-After header, matched case-insensitively like slack_sdk does."""
    headers = getattr(exc.response, "headers", None)
    if not isinstance(headers, dict):
        return None
    for name, value in headers.items():
        if name.lower() == "retry-after":
            raw = value[0] if isinstance(value, list) and value else value
            try:
                return int(str(raw))
            except ValueError:
                return None
    return None
