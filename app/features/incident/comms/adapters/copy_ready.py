"""Copy-ready ``StatusPagePublisher``: renders the text for a person to paste.

Publishes nowhere, so it has no side effects and cannot fail beyond refusing a
draft.
"""

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText
from features.incident.comms.publisher import render_copy_ready
from features.incident.core.api import StatusUpdate, StatusUpdateState


class CopyReadyPublisher:
    """``StatusPagePublisher`` returning the update as structured plain text."""

    async def publish(
        self,
        update: StatusUpdate,
        *,
        labels_en: ProfileLabels,
        labels_fr: ProfileLabels,
    ) -> OperationResult[CopyReadyText]:
        """Return ``render_copy_ready`` of an approved update; refuse a draft."""
        if update.state is StatusUpdateState.DRAFT:
            return OperationResult.permanent_error(
                message="A draft status update is not approved, so it has no copy-ready text",
                error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED,
            )
        return OperationResult.success(data=render_copy_ready(update, labels_en, labels_fr))
