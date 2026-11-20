"""AI writer for a process with no model endpoint configured: never available, every call a permanent error."""

from collections.abc import Sequence

from capabilities.ai_writing.api import AIWriter, FilledTemplate, TemplateField, TemplateSection
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult


class UnconfiguredAIWriter(AIWriter):
    """``AIWriter`` that reaches no model: unavailable is an outcome, never an error."""

    def is_available(self) -> bool:
        """Never available: no endpoint backs it."""
        return False

    async def write(
        self, source: str, *, instructions: str, max_output_tokens: int, temperature: float | None = None
    ) -> OperationResult[str]:
        """Return ``AI_WRITING_UNAVAILABLE`` without reaching any model."""
        return OperationResult.permanent_error(
            message="AI writing is not configured",
            error_code=ErrorCode.AI_WRITING_UNAVAILABLE,
        )

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
        """Return ``AI_WRITING_UNAVAILABLE`` without reaching any model."""
        return OperationResult.permanent_error(
            message="AI writing is not configured",
            error_code=ErrorCode.AI_WRITING_UNAVAILABLE,
        )
