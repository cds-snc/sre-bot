"""Summarizer behavior port and its OpenAI-backed adapter.

``Summarizer`` is the narrow behavior contract feature packages depend on
(per the model-boundary rules: ``Protocol`` for service contracts). The
``OpenAISummarizer`` adapter is the boundary tier: it calls the vendor client inside
``try/except``, classifies failures via ``classify_openai_error``, and
returns ``OperationResult``. Unmapped exceptions propagate -- they are bugs,
not outcomes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

import structlog

from infrastructure.operations.result import OperationResult
from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings, get_openai_settings

logger = structlog.get_logger()

_DEFAULT_INSTRUCTIONS = (
    "You are an incident-response assistant. Summarize the following chat "
    "transcript from an incident channel so that a responder joining now can "
    "quickly catch up. Be concise and factual. Cover: what is happening, "
    "current status, actions taken, and next steps. Do not invent details "
    "that are not in the transcript."
)


@runtime_checkable
class Summarizer(Protocol):
    """Behavior contract for producing a text summary of a transcript."""

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        """Return an ``OperationResult`` carrying the summary text on success."""
        ...


class OpenAISummarizer:
    """``Summarizer`` implementation backed by the OpenAI chat completions API."""

    def __init__(self, settings: OpenAISettings | None = None) -> None:
        self._settings = settings or get_openai_settings()

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        """Summarize ``transcript`` via the OpenAI chat completions endpoint.

        Args:
            transcript: The user content to summarize.
            instructions: Optional system prompt replacing the default.
            max_output_tokens: Optional per-call completion budget. Callers
                that need substantially more output than a catch-up summary
                (e.g. structured multi-section drafts) raise it; ``None`` uses
                the configured ``MAX_OUTPUT_TOKENS``.
        """
        payload: dict[str, Any] = {
            "model": self._settings.MODEL,
            "max_completion_tokens": max_output_tokens or self._settings.MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": instructions or _DEFAULT_INSTRUCTIONS},
                {"role": "user", "content": transcript},
            ],
        }
        if self._settings.TEMPERATURE >= 0:
            # Omitted when negative: some models accept no temperature at all,
            # and a rejected parameter fails the whole request.
            payload["temperature"] = self._settings.TEMPERATURE

        try:
            async with build_openai_client(self._settings) as client:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            # The status alone does not say what the API objected to; a 400's
            # body names the offending parameter, which is the difference
            # between diagnosing this and guessing at it.
            logger.warning(
                "openai_summarize_failed",
                error=str(exc),
                response_body=_error_body(exc),
                sent_parameters=sorted(payload),
            )
            return classify_openai_error(exc)

        summary = _extract_summary(body)
        finish_reason = _finish_reason(body)
        if finish_reason == "length":
            # The completion budget ran out mid-response, so the text is cut
            # off. Callers parsing structured output need to know this.
            logger.warning(
                "openai_summarize_truncated",
                max_completion_tokens=payload["max_completion_tokens"],
                summary_length=len(summary),
            )
        elif not summary:
            logger.warning("openai_summarize_empty_content", finish_reason=finish_reason)

        return OperationResult.success(
            data=summary,
            provider="openai",
            operation="summarize",
        )


def _error_body(exc: Exception) -> str:
    """Return the API's error body, truncated, when the failure carries one."""
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        return str(response.text)[:500]
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real error
        return ""


def _extract_summary(body: dict) -> str:
    """Pull the assistant message text out of a chat completions response."""
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def _finish_reason(body: dict) -> str | None:
    """Return the first choice's ``finish_reason`` (``"length"`` when truncated)."""
    choices = body.get("choices") or []
    if not choices:
        return None
    reason = choices[0].get("finish_reason")
    return str(reason) if reason is not None else None


@lru_cache(maxsize=1)
def get_summarizer() -> OpenAISummarizer:
    """Return the process-wide ``OpenAISummarizer`` singleton (the ``Summarizer`` port)."""
    return OpenAISummarizer()
