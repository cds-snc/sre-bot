"""Interfaces the incident comms use case depends on.

The services consume these Protocols and ``providers.py`` binds them to the
adapters, so both import them from here rather than from each other.
"""

from typing import Protocol, runtime_checkable

from contracts.operations import OperationResult
from features.incident.comms.domain import CopyReadyText, ProfileLabels
from features.incident.core.api import StatusUpdate


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
