"""OpenAI adapter of the AI writing capability: the chat completions API behind ``AIWriter``.

The capability's only importer of ``integrations.openai`` (import-linter contract (o)). It calls
the vendor client inside ``try/except``, classifies failures via ``classify_openai_error`` and
returns ``OperationResult``; unmapped exceptions propagate, as they are bugs, not outcomes. The
output budget and temperature are the caller's, per call; the model is read from the OpenAI slice.
"""

from typing import Any

import structlog

from capabilities.ai_writing.api import AIWriter
from contracts.operations.result import OperationResult
from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings, get_openai_settings

logger = structlog.get_logger()


class OpenAIWriter(AIWriter):
    """``AIWriter`` backed by an OpenAI-compatible chat completions endpoint."""

    def __init__(self, settings: OpenAISettings | None = None) -> None:
        self._settings = settings or get_openai_settings()

    def is_available(self) -> bool:
        """Always available: the provider builds this adapter only for a configured tenant."""
        return True

    async def write(
        self, source: str, *, instructions: str, max_output_tokens: int, temperature: float | None = None
    ) -> OperationResult[str]:
        """Write text from ``source`` under ``instructions`` via the chat completions endpoint.

        Args:
            source: The user content.
            instructions: The system prompt.
            max_output_tokens: The completion budget, sent as ``max_completion_tokens``.
            temperature: Sent only when set: some models accept no temperature at all, and a
                rejected parameter fails the whole request.
        """
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "max_completion_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": source},
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature

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
                "openai_write_failed",
                error=str(exc),
                response_body=_error_body(exc),
                sent_parameters=sorted(payload),
            )
            status, error_code, retry_after = classify_openai_error(exc)
            return OperationResult.error(
                status,
                f"OpenAI request failed ({error_code})",
                error_code=error_code,
                retry_after=retry_after,
            )

        text = _extract_text(body)
        finish_reason = _finish_reason(body)
        usage = _usage(body)
        logger.info(
            "openai_write_usage",
            model=payload["model"],
            finish_reason=finish_reason,
            max_completion_tokens=payload["max_completion_tokens"],
            text_length=len(text),
            **usage,
        )
        if finish_reason == "length":
            # The completion budget ran out mid-response, so the text is cut
            # off. Callers parsing structured output need to know this.
            logger.warning(
                "openai_write_truncated",
                max_completion_tokens=payload["max_completion_tokens"],
                text_length=len(text),
                **usage,
            )
        elif not text:
            logger.warning("openai_write_empty_content", finish_reason=finish_reason)

        return OperationResult.success(data=text)


def _error_body(exc: Exception) -> str:
    """Return the API's error body, truncated, when the failure carries one."""
    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        return str(response.text)[:500]
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real error
        return ""


def _extract_text(body: dict) -> str:
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


def _usage(body: dict) -> dict[str, int]:
    """Return the response's token counts, including reasoning tokens.

    ``max_completion_tokens`` bounds reasoning *plus* visible output on
    reasoning models, so a prompt that provokes more deliberation silently
    leaves less room for the answer. Without ``reasoning_tokens`` a short
    response is indistinguishable from the model simply having little to say.
    """
    usage = body.get("usage") or {}
    counts = {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
    }
    return {key: int(value) for key, value in counts.items() if isinstance(value, int)}


def build_openai_writer() -> OpenAIWriter | None:
    """Return the OpenAI writer when [openai.tenant] is set, else ``None`` (no client is built either way)."""
    settings = get_openai_settings()
    if settings.tenant is None:
        return None
    return OpenAIWriter(settings)
