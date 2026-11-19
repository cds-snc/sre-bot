"""Public surface of the AI writing capability: its Protocol and provider function.

Features import this module only (decisions/plugin-architecture.md).

The capability has one purpose: a language model writes text (a summary, a draft, a template
filled section by section) from a source and the caller's instructions. Any other AI use is a
separate capability named for its purpose.

The capability is always present: ``get_ai_writer()`` always resolves, and when no model endpoint
is configured the writer answers ``is_available()`` false and ``AI_WRITING_UNAVAILABLE`` on every
call. A consumer offering an optional action asks ``is_available()`` first.
"""

from typing import Protocol

from contracts.operations.result import OperationResult


class AIWriter(Protocol):
    """Writes text with a language model from a source and the caller's instructions."""

    def is_available(self) -> bool:
        """Whether a model endpoint backs this writer, so an optional action may be offered."""
        ...

    async def write(self, source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]:
        """Return the written text, or the classified error (``AI_WRITING_UNAVAILABLE`` when unbacked).

        Args:
            source: The content the text is written from (a transcript, a draft).
            instructions: The caller's system prompt; every caller states its own.
            max_output_tokens: Optional per-call completion budget; ``None`` uses the configured one.
        """
        ...


def get_ai_writer() -> AIWriter:
    """Return the process AI writer: backed by the configured endpoint, or one reporting unavailable."""
    from capabilities.ai_writing.providers import get_ai_writer_singleton  # noqa: PLC0415 - adapters import this module

    return get_ai_writer_singleton()
