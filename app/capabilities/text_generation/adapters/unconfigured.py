"""Text generator for a process with no model endpoint configured: available never, every call a permanent error."""

from capabilities.text_generation.api import TextGenerator
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult


class UnconfiguredTextGenerator(TextGenerator):
    """``TextGenerator`` that reaches no provider: unavailable is an outcome, never an error."""

    def is_available(self) -> bool:
        """Never available: no endpoint backs it."""
        return False

    async def generate(self, source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]:
        """Return ``TEXT_GENERATION_UNAVAILABLE`` without reaching any provider."""
        return OperationResult.permanent_error(
            message="Text generation is not configured",
            error_code=ErrorCode.TEXT_GENERATION_UNAVAILABLE,
        )
