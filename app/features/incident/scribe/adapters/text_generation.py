"""Text-generation adapter for status updates, over the OpenAI ``Summarizer``.

The status-update service depends on its own ``TextGenerator`` interface; this
is the one place that interface is bound to an integration. It becomes the
text-generation capability with TASK-134.

When the OpenAI settings cannot load (no API key), the binding is a generator
that reports ``TEXT_GENERATION_UNAVAILABLE`` on every call, so drafting falls
back to a hand-written update instead of failing.
"""

import structlog
from pydantic import ValidationError

from contracts.operations import OperationResult
from features.incident.scribe.ports import TextGenerator
from integrations.openai import get_summarizer

logger = structlog.get_logger()

TEXT_GENERATION_UNAVAILABLE_CODE = "TEXT_GENERATION_UNAVAILABLE"


class UnavailableTextGenerator:
    """``TextGenerator`` for an unconfigured integration: every call is a permanent error."""

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        """Return ``TEXT_GENERATION_UNAVAILABLE`` without reaching any provider."""
        return OperationResult.permanent_error(
            message="Text generation is not configured",
            error_code=TEXT_GENERATION_UNAVAILABLE_CODE,
        )


def build_status_update_text_generator() -> TextGenerator:
    """Return the process ``Summarizer``, or ``UnavailableTextGenerator`` when its settings cannot load."""
    try:
        return get_summarizer()
    except ValidationError as error:
        # Field names only: a validation error's text can echo configured values.
        fields = [".".join(str(part) for part in detail["loc"]) for detail in error.errors()]
        logger.warning("incident_status_update_text_generation_unconfigured", fields=fields)
        return UnavailableTextGenerator()
