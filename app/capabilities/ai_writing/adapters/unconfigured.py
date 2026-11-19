"""AI writer for a process with no model endpoint configured: never available, every call a permanent error."""

from capabilities.ai_writing.api import AIWriter
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult


class UnconfiguredAIWriter(AIWriter):
    """``AIWriter`` that reaches no model: unavailable is an outcome, never an error."""

    def is_available(self) -> bool:
        """Never available: no endpoint backs it."""
        return False

    async def write(self, source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]:
        """Return ``AI_WRITING_UNAVAILABLE`` without reaching any model."""
        return OperationResult.permanent_error(
            message="AI writing is not configured",
            error_code=ErrorCode.AI_WRITING_UNAVAILABLE,
        )
