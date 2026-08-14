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
from typing import Protocol, runtime_checkable

import structlog

from infrastructure.operations.result import OperationResult
from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings, get_openai_settings

logger = structlog.get_logger()

_DEFAULT_INSTRUCTIONS = (
    "You are an incident-response assistant. Summarize the following chat "
    "transcript from an incident channel so that a responder joining now can "
    "quickly catch up. Be concise and factual. Cover: what is happening, key "
    "events in order, current status, actions taken, and any open questions or "
    "next steps. Do not invent details that are not in the transcript."
)


@runtime_checkable
class Summarizer(Protocol):
    """Behavior contract for producing a text summary of a transcript."""

    async def summarize(self, transcript: str, *, instructions: str | None = None) -> OperationResult[str]:
        """Return an ``OperationResult`` carrying the summary text on success."""
        ...


class OpenAISummarizer:
    """``Summarizer`` implementation backed by the OpenAI chat completions API."""

    def __init__(self, settings: OpenAISettings | None = None) -> None:
        self._settings = settings or get_openai_settings()

    async def summarize(self, transcript: str, *, instructions: str | None = None) -> OperationResult[str]:
        """Summarize ``transcript`` via the OpenAI chat completions endpoint."""
        payload = {
            "model": self._settings.MODEL,
            "max_completion_tokens": self._settings.MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": instructions or _DEFAULT_INSTRUCTIONS},
                {"role": "user", "content": transcript},
            ],
        }

        try:
            async with build_openai_client(self._settings) as client:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            logger.warning("openai_summarize_failed", error=str(exc))
            return classify_openai_error(exc)

        summary = _extract_summary(body)
        return OperationResult.success(
            data=summary,
            provider="openai",
            operation="summarize",
        )


def _extract_summary(body: dict) -> str:
    """Pull the assistant message text out of a chat completions response."""
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


@lru_cache(maxsize=1)
def get_summarizer() -> OpenAISummarizer:
    """Return the process-wide ``OpenAISummarizer`` singleton (the ``Summarizer`` port)."""
    return OpenAISummarizer()
