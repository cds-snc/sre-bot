"""In-memory AI writer for tests and local runs, with the real writers' observable rules.

Available, it answers ``respond(source, instructions)`` (a fixed text by default) or a scripted
result; unavailable, it answers ``AI_WRITING_UNAVAILABLE`` like the unconfigured writer.
Every call is recorded.
"""

from collections.abc import Callable
from dataclasses import dataclass

from capabilities.ai_writing.api import AIWriter
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult


@dataclass(frozen=True)
class WritingCall:
    """One recorded ``write`` call."""

    source: str
    instructions: str
    max_output_tokens: int | None


class InMemoryAIWriter(AIWriter):
    """``AIWriter`` answering from a function or a scripted result, recording each call."""

    def __init__(
        self,
        *,
        available: bool = True,
        respond: Callable[[str, str], str] | None = None,
        result: OperationResult[str] | None = None,
    ) -> None:
        self._available = available
        self._respond = respond or (lambda source, instructions: "written text")
        self._result = result
        self.calls: list[WritingCall] = []

    def is_available(self) -> bool:
        """Return the ``available`` the fake was built with."""
        return self._available

    async def write(self, source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]:
        """Record the call, then answer unavailable, the scripted result, or the response text."""
        self.calls.append(WritingCall(source, instructions, max_output_tokens))
        if not self._available:
            return OperationResult.permanent_error(
                message="AI writing is not configured",
                error_code=ErrorCode.AI_WRITING_UNAVAILABLE,
            )
        if self._result is not None:
            return self._result
        return OperationResult.success(data=self._respond(source, instructions))
