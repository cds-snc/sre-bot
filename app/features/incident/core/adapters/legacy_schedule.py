"""Interim read of a report placement's on-call schedule from its Drive folder's ``genie_schedule`` property.

The legacy declare kept each product folder's Opsgenie schedule id as the folder's
Drive ``appProperties`` ``genie_schedule``. Until the product catalogue holds a
product's ``ScheduleReference`` (TASK-165.1, which imports these values once), declare
reads it here, read only, and asks the on-call capability with it. The one Opsgenie
name in the incident umbrella is the capability's ``OPSGENIE`` system constant, tolerated
here with owner TASK-165.1 (decisions/oncall.md, decisions/incident-management.md).

TODO(TASK-165.1): delete with ``PlacementScheduleLookup`` once the catalogue answers it.
"""

import asyncio

from googleapiclient.errors import HttpError

from capabilities.oncall.api import OPSGENIE, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters import google_docs
from features.incident.core.domain import ReportPlacement
from integrations.google_workspace.client import classify_google_error

_SCHEDULE_PROPERTY = "genie_schedule"


class GoogleDrivePlacementScheduleLookup:
    """Read a Google placement folder's schedule property; the single blocking call runs in one thread."""

    async def schedule_for(self, placement: ReportPlacement) -> OperationResult[ScheduleReference | None]:
        """Return the folder's schedule, ``None`` when the property is missing or blank.

        Another system's placement is PERMANENT_ERROR with ``UNSUPPORTED_OPERATION`` without a
        call; a Drive failure is the classified result, already logged by the Drive call.
        """
        if placement.system is not WorkplaceSystem.GOOGLE:
            return OperationResult.permanent_error(
                f"Google Drive cannot reach a placement on {placement.system.value}", ErrorCode.UNSUPPORTED_OPERATION
            )
        try:
            metadata = await asyncio.to_thread(google_docs.get_metadata, placement.vendor_id, "appProperties")
        except HttpError as exc:
            status, error_code, retry_after = classify_google_error(exc)
            return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
        schedule_id = str((metadata.get("appProperties") or {}).get(_SCHEDULE_PROPERTY) or "").strip()
        return OperationResult.success(ScheduleReference(system=OPSGENIE, id=schedule_id) if schedule_id else None)
