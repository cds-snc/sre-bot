"""Interfaces the incident comms use case depends on.

The services consume these Protocols and ``providers.py`` binds them to the
adapters, so both import them from here rather than from each other.
"""

from typing import Protocol, runtime_checkable

from contracts.operations import OperationResult
from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText
from features.incident.core.api import StatusUpdate


@runtime_checkable
class TextGenerator(Protocol):
    """Interface producing text from a transcript and instructions."""

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        """Return the generated text, or the provider's classified error."""
        ...


@runtime_checkable
class StatusPagePublisher(Protocol):
    """Interface turning an approved status update into the text for a status page."""

    async def publish(
        self,
        update: StatusUpdate,
        *,
        labels_en: ProfileLabels,
        labels_fr: ProfileLabels,
    ) -> OperationResult[CopyReadyText]:
        """Return the update's text per language, or ``STATUS_UPDATE_NOT_APPROVED`` for a draft."""
        ...
