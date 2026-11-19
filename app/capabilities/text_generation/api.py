"""Public surface of the Text generation capability: its Protocol, domain types and provider function.

Features import this module only (decisions/plugin-architecture.md).

The capability is always present: ``get_text_generator()`` always resolves, and when no model
endpoint is configured the generator answers ``is_available()`` false and
``TEXT_GENERATION_UNAVAILABLE`` on every call. A consumer offering an optional action asks
``is_available()`` first.
"""

from typing import Protocol

from contracts.operations.result import OperationResult


class TextGenerator(Protocol):
    """Produces text from a source and the caller's instructions."""

    def is_available(self) -> bool:
        """Whether a model endpoint backs this generator, so an optional action may be offered."""
        ...

    async def generate(self, source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]:
        """Return the generated text, or the classified error (``TEXT_GENERATION_UNAVAILABLE`` when unbacked).

        Args:
            source: The content the text is generated from (a transcript, a draft).
            instructions: The caller's system prompt; every caller states its own.
            max_output_tokens: Optional per-call completion budget; ``None`` uses the configured one.
        """
        ...


def get_text_generator() -> TextGenerator:
    """Return the process text generator: backed by the configured endpoint, or one reporting unavailable."""
    from capabilities.text_generation.providers import get_text_generator_singleton  # noqa: PLC0415 - adapters import this module

    return get_text_generator_singleton()
