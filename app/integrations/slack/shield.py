"""Slack shield: resilience boundary around `slack_sdk.AsyncWebClient`.

Exposes `SlackShield` — constructs an `AsyncWebClient` with three SDK-native
retry handlers at construction (connection errors, rate-limit responses, 5xx
server errors) and provides the three executor entry points:

- `execute(aw)` — shape α: awaitable executor for Web API calls
- `execute_say(method, **kwargs)` — shape β: entry for say (chat_postMessage)
- `execute_respond(aw)` — shape β: entry for respond (webhook POST)

Two classification tables live in this file as the single source of truth:
- Web API path (`SlackApiError`-based) — used by `execute` and `execute_say`
- Webhook path (HTTP-status-based) — used by `execute_respond`

`ShieldedSay` and `ShieldedRespond` expose Bolt's native callable signatures
and return `OperationResult`. Handlers receive them via the
`shield_listener_callables` middleware; the shield is invisible at call sites.

Adapter call shapes:

    # Direct Web API (shape α)
    result = await shield.execute(
        shield.web.chat_postMessage(channel=channel_id, text=message)
    )

    # Via ShieldedSay (shape β — set by middleware; handlers just call say())
    result = await say(text="hello", thread_ts=ts)

    # Via ShieldedRespond (shape β — set by middleware; handlers just call respond())
    result = await respond(text="hello", replace_original=True)
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.async_handler import AsyncRetryHandler
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncConnectionErrorRetryHandler,
    AsyncRateLimitErrorRetryHandler,
    AsyncServerErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings

R = TypeVar("R")

_PROVIDER = "slack"
_TIMEOUT_ERROR_CODE = "request_timeout"


class SlackShield:
    """Resilience boundary around `slack_sdk.AsyncWebClient`.

    Owns SDK construction with native retry handlers, applies the per-call
    time budget at executor boundaries, and converts SDK errors into
    `OperationResult` envelopes using the two classification tables below.
    """

    def __init__(self, settings: SlackSettings) -> None:
        self._settings = settings
        retry_handlers: list[AsyncRetryHandler] = [
            AsyncConnectionErrorRetryHandler(
                max_retry_count=settings.RETRY_MAX_ATTEMPTS
            ),
            AsyncRateLimitErrorRetryHandler(
                max_retry_count=settings.RETRY_MAX_ATTEMPTS
            ),
            AsyncServerErrorRetryHandler(max_retry_count=settings.RETRY_MAX_ATTEMPTS),
        ]
        self.web: AsyncWebClient = AsyncWebClient(
            token=settings.BOT_TOKEN,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            retry_handlers=retry_handlers,
        )

        self._not_found_codes: frozenset[str] = frozenset(settings.NOT_FOUND_CODES)
        self._unauthorized_codes: frozenset[str] = frozenset(
            settings.UNAUTHORIZED_CODES
        )
        self._transient_codes: frozenset[str] = frozenset(settings.TRANSIENT_CODES)

    # ------------------------------------------------------------------ #
    # Web API path (shape α)                                               #
    # ------------------------------------------------------------------ #

    async def execute(self, aw: Awaitable[R]) -> OperationResult[R]:
        """Await `aw` under the per-call budget and classify any error.

        Classification table — Web API path:
        | Condition                                        | Status           |
        | channel_not_found / user_not_found / …          | NOT_FOUND        |
        | not_authed / invalid_auth / missing_scope / …   | UNAUTHORIZED     |
        | ratelimited (post-retry)                         | TRANSIENT_ERROR  |
        | fatal_error / internal_error / … (post-retry)   | TRANSIENT_ERROR  |
        | asyncio.TimeoutError                             | TRANSIENT_ERROR  |
        | any other Slack error code                       | PERMANENT_ERROR  |
        | any other exception                              | PERMANENT_ERROR  |
        """
        try:
            data = await asyncio.wait_for(
                aw, timeout=self._settings.REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return OperationResult.transient_error(
                message="slack request exceeded per-call time budget",
                error_code=_TIMEOUT_ERROR_CODE,
            )
        except SlackApiError as exc:
            return self._classify_slack_error(exc)
        except Exception as exc:
            return OperationResult.permanent_error(
                message=str(exc),
                error_code="unexpected_error",
            )

        return OperationResult.success(data=data, provider=_PROVIDER)

    # ------------------------------------------------------------------ #
    # say path (shape β)                                                   #
    # ------------------------------------------------------------------ #

    async def execute_say(
        self, method: Callable[..., Awaitable[R]], **kwargs: Any
    ) -> OperationResult[R]:
        """Shape β entry for say. Calls `method(**kwargs)` to produce the coroutine."""
        return await self.execute(method(**kwargs))

    # ------------------------------------------------------------------ #
    # Webhook path (shape β)                                               #
    # ------------------------------------------------------------------ #

    async def execute_respond(self, aw: Awaitable[Any]) -> OperationResult[Any]:
        """Await a webhook send coroutine and classify by HTTP status.

        Classification table — webhook path:
        | Condition                             | Status           |
        | HTTP 200                              | SUCCESS          |
        | HTTP 404 (expired/invalid URL)        | PERMANENT_ERROR  |
        | HTTP 429                              | TRANSIENT_ERROR  |
        | HTTP 5xx                              | TRANSIENT_ERROR  |
        | asyncio.TimeoutError                  | TRANSIENT_ERROR  |
        | ValueError (missing URL / bad type)   | PERMANENT_ERROR  |
        | any other exception                   | PERMANENT_ERROR  |
        """
        try:
            response = await asyncio.wait_for(
                aw, timeout=self._settings.REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return OperationResult.transient_error(
                message="slack webhook request exceeded per-call time budget",
                error_code=_TIMEOUT_ERROR_CODE,
            )
        except ValueError as exc:
            return OperationResult.permanent_error(
                message=str(exc),
                error_code="webhook_value_error",
            )
        except Exception as exc:
            return OperationResult.permanent_error(
                message=str(exc),
                error_code="webhook_error",
            )

        return self._classify_webhook_response(response)

    # ------------------------------------------------------------------ #
    # Classification helpers                                               #
    # ------------------------------------------------------------------ #

    def _classify_slack_error(self, exc: SlackApiError) -> OperationResult[Any]:
        """Map a `SlackApiError` to an `OperationResult` using its error code."""
        response = getattr(exc, "response", None)
        data = getattr(response, "data", None) if response is not None else None
        if not isinstance(data, dict):
            data = {}
        code: str = data.get("error") or ""
        message: str = code or str(exc)
        retry_after = _extract_retry_after(response)

        if code in self._not_found_codes:
            status = OperationStatus.NOT_FOUND
        elif code in self._unauthorized_codes:
            status = OperationStatus.UNAUTHORIZED
        elif code in self._transient_codes:
            status = OperationStatus.TRANSIENT_ERROR
        else:
            status = OperationStatus.PERMANENT_ERROR

        return OperationResult.error(
            status=status,
            message=message,
            error_code=code or None,
            retry_after=retry_after,
            provider=_PROVIDER,
        )

    def _classify_webhook_response(self, response: Any) -> OperationResult[Any]:
        """Classify a `WebhookResponse` by HTTP status code."""
        status_code: int = getattr(response, "status_code", 0)

        if status_code == 200:
            return OperationResult.success(data=response, provider=_PROVIDER)

        retry_after = _extract_retry_after(response)

        if status_code == 404:
            return OperationResult.permanent_error(
                message="webhook response_url is invalid or expired (HTTP 404)",
                error_code="webhook_not_found",
            )
        if status_code == 429:
            return OperationResult.transient_error(
                message="webhook rate limited (HTTP 429)",
                error_code="webhook_ratelimited",
                retry_after=retry_after,
            )
        if 500 <= status_code < 600:
            return OperationResult.transient_error(
                message=f"webhook server error (HTTP {status_code})",
                error_code="webhook_server_error",
            )
        return OperationResult.permanent_error(
            message=f"webhook error (HTTP {status_code})",
            error_code="webhook_error",
        )


# ------------------------------------------------------------------ #
# Shielded callables — Bolt-compatible wrappers                        #
# ------------------------------------------------------------------ #


class ShieldedSay:
    """Bolt-compatible `say` callable backed by `shield.execute_say`.

    Constructed by `shield_listener_callables` middleware with the
    channel and thread_ts from `BoltContext`. Handlers call it with
    the same syntax as Bolt's native `say` and receive `OperationResult`.
    """

    def __init__(
        self,
        shield: SlackShield,
        channel: str,
        thread_ts: Optional[str] = None,
    ) -> None:
        self._shield = shield
        self._channel = channel
        self._thread_ts = thread_ts

    async def __call__(
        self,
        text: Optional[str] = None,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
        **kwargs: Any,
    ) -> OperationResult[Any]:
        return await self._shield.execute_say(
            self._shield.web.chat_postMessage,
            channel=self._channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts or self._thread_ts,
            **kwargs,
        )


class ShieldedRespond:
    """Bolt-compatible `respond` callable backed by `shield.execute_respond`.

    Constructed by `shield_listener_callables` middleware with the
    `response_url` from `BoltContext`. Handlers call it with the same
    syntax as Bolt's native `respond` and receive `OperationResult`.

    Note: `response_url` is valid for 30 minutes and accepts at most 5
    responses per interaction. This quota is not enforced per-call; the
    adapter is responsible for tracking it when calling respond repeatedly.
    """

    def __init__(
        self,
        shield: SlackShield,
        response_url: Optional[str] = None,
    ) -> None:
        self._shield = shield
        self._client: Optional[AsyncWebhookClient] = (
            AsyncWebhookClient(url=response_url) if response_url else None
        )

    async def __call__(
        self,
        text: Optional[str] = None,
        blocks: Optional[list] = None,
        replace_original: bool = False,
        **kwargs: Any,
    ) -> OperationResult[Any]:
        if self._client is None:
            return OperationResult.permanent_error(
                message="respond called with no response_url in this context",
                error_code="missing_response_url",
            )
        return await self._shield.execute_respond(
            self._client.send(
                text=text,
                blocks=blocks,
                replace_original=replace_original,
                **kwargs,
            )
        )


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _extract_retry_after(response: Any) -> Optional[int]:
    """Read the `Retry-After` header off a Slack response, if present."""
    headers: Dict[str, Any] = getattr(response, "headers", None) or {}
    raw = headers.get("Retry-After") if isinstance(headers, dict) else None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
