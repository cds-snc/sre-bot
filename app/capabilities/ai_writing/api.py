"""Public surface of the AI writing capability: its Protocol and provider function.

Features import this module only (decisions/plugin-architecture.md).

The capability has one purpose: a language model writes text (a summary, a draft, a template
filled section by section) from a source and the caller's instructions. Any other AI use is a
separate capability named for its purpose.

The capability is always present: ``get_ai_writer()`` always resolves, and when no model endpoint
is configured the writer answers ``is_available()`` false and ``AI_WRITING_UNAVAILABLE`` on every
call. A consumer offering an optional action asks ``is_available()`` first.
"""

from collections.abc import Sequence
from typing import Protocol

from capabilities.ai_writing.domain import (
    FilledTemplate,
    TemplateAnswer,
    TemplateField,
    TemplateSection,
    extract_json_object,
)
from contracts.operations.result import OperationResult

__all__ = [
    "AIWriter",
    "FilledTemplate",
    "TemplateAnswer",
    "TemplateField",
    "TemplateSection",
    "extract_json_object",
    "get_ai_writer",
]


class AIWriter(Protocol):
    """Writes text with a language model from a source and the caller's instructions."""

    def is_available(self) -> bool:
        """Whether a model endpoint backs this writer, so an optional action may be offered."""
        ...

    async def write(
        self, source: str, *, instructions: str, max_output_tokens: int, temperature: float | None = None
    ) -> OperationResult[str]:
        """Return the written text, or the classified error (``AI_WRITING_UNAVAILABLE`` when unbacked).

        Args:
            source: The content the text is written from (a document, a draft, a message log).
            instructions: The caller's system prompt; every caller states its own.
            max_output_tokens: The completion budget; every caller states its own.
            temperature: Optional sampling temperature, omitted from the request when ``None``
                (some models reject the parameter outright).
        """
        ...

    async def fill_template(
        self,
        source: str,
        *,
        sections: Sequence[TemplateSection],
        instructions: str,
        max_output_tokens: int,
        temperature: float | None = None,
        fields: Sequence[TemplateField] = (),
    ) -> OperationResult[FilledTemplate]:
        """Fill a template section by section from ``source`` in one model call.

        Returns one answer per section and field in request order, ``truncated`` when the model's
        answer was cut off and only its complete pairs were kept; the write's classified error;
        ``AI_WRITING_UNPARSEABLE`` when nothing usable came back; ``AI_WRITING_UNAVAILABLE`` when
        unbacked.

        Args:
            source: The content the template is filled from, sent last and verbatim.
            sections: The headings to answer, each with its instructions, in order.
            instructions: The caller's system prompt, asking for one JSON object keyed by heading.
            max_output_tokens: The completion budget, as for ``write``.
            temperature: Optional sampling temperature, as for ``write``.
            fields: Short values filled in the same JSON object, keyed by label.
        """
        ...


def get_ai_writer() -> AIWriter:
    """Return the process AI writer: backed by the configured endpoint, or one reporting unavailable."""
    from capabilities.ai_writing.providers import get_ai_writer_singleton  # noqa: PLC0415 - adapters import this module

    return get_ai_writer_singleton()
