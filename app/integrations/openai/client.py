"""OpenAI vendor client: authenticated client factory and error
classification.

This module provides authenticated client construction and ``classify_openai_error``.
exceptions and contains no business logic. The adapter in
``app.integrations.openai.summarizer`` is the boundary that calls into this
module inside ``try/except`` and classifies.
"""

from __future__ import annotations

import contextlib

import httpx

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.openai.settings import OpenAISettings, get_openai_settings


def build_openai_client(settings: OpenAISettings | None = None) -> httpx.AsyncClient:
    """Build an authenticated httpx client for the OpenAI REST API.

    Caller manages the client's lifecycle (use as an async context manager).
    """
    settings = settings or get_openai_settings()
    return httpx.AsyncClient(
        base_url=settings.BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.API_KEY.get_secret_value()}",
            "Content-Type": "application/json",
        },
        timeout=settings.TIMEOUT_SECONDS,
    )


def classify_openai_error(exc: Exception) -> OperationResult:
    """Map OpenAI/HTTP exceptions to ``OperationResult``.

    Unmapped exceptions propagate uncaught -- they are bugs, not outcomes.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status_code = response.status_code

        if status_code == 401:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                "OpenAI authentication failed",
                error_code="UNAUTHORIZED",
                provider="openai",
            )
        if status_code == 403:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                "OpenAI API access forbidden",
                error_code="FORBIDDEN",
                provider="openai",
            )
        if status_code == 404:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                "OpenAI resource not found",
                error_code="NOT_FOUND",
                provider="openai",
            )
        if status_code == 429:
            retry_after = 60
            header_value = response.headers.get("Retry-After")
            if header_value:
                with contextlib.suppress(TypeError, ValueError):
                    retry_after = int(header_value)
            return OperationResult.error(
                OperationStatus.TRANSIENT_ERROR,
                "OpenAI API rate limited",
                error_code="RATE_LIMITED",
                retry_after=retry_after,
                provider="openai",
            )
        if 500 <= status_code < 600:
            return OperationResult.error(
                OperationStatus.TRANSIENT_ERROR,
                f"OpenAI API server error ({status_code})",
                error_code="SERVER_ERROR",
                provider="openai",
            )
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            f"OpenAI API client error ({status_code})",
            error_code="HTTP_ERROR",
            provider="openai",
        )

    if isinstance(exc, httpx.TimeoutException):
        return OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "OpenAI API request timed out",
            error_code="TIMEOUT",
            provider="openai",
        )

    if isinstance(exc, httpx.HTTPError):
        return OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "OpenAI API request failed",
            error_code="CONNECTION_ERROR",
            provider="openai",
        )

    raise exc
