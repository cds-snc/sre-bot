"""Google Sheets adapter of the incident core: the incident list projection.

The only module in features/incident/ that reaches Google Sheets, through
``integrations.google_workspace`` (never ``infrastructure.spreadsheets``).
``GoogleSheetsIncidentListProjection`` is the ``IncidentListProjection`` behind
``core.api``: each method runs one blocking function through ``asyncio.to_thread``
that looks the incident's row up by its id (column F, falling back to the
channel in column E for rows written before F existed) and then rewrites,
updates or appends it. The sheet is written, never read as a source of truth
(decisions/workplace-systems.md, rule 5). Settings are read at call time.
"""

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Literal

import structlog
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.list_rows import list_row, row_index_for
from features.incident.core.adapters.slack import slack_conversation_label, slack_conversation_link
from features.incident.core.domain import Incident
from integrations.google_workspace.client import GoogleCredentialsRefused, classify_google_error, get_sheets_service
from integrations.google_workspace.settings import get_google_workspace_settings

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import ValueRange  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_INPUT: Literal["USER_ENTERED"] = "USER_ENTERED"
_UNPARSABLE_RANGE = "Unable to parse range"


def _write_row(spreadsheet_id: str, incident: Incident, row: list[str], *, status_only: bool) -> None:
    """Upsert the incident's row; blocking.

    Reads E:F as typed, then updates the row found (A:F, or D and, for a row found by channel, F) or appends
    the full row once: an append has no idempotency key, so its SDK retry is off.
    """
    values = get_sheets_service(scopes=SHEETS_SCOPES).spreadsheets().values()
    found = values.get(spreadsheetId=spreadsheet_id, range="Sheet1!E:F", valueRenderOption="FORMULA").execute()
    channel_id = incident.conversation.vendor_id if incident.conversation is not None else None
    body: ValueRange = {"values": [row]}
    match = row_index_for(incident.id, channel_id, found.get("values", []))
    if match is None:
        values.append(
            spreadsheetId=spreadsheet_id, range="Sheet1!A:A", valueInputOption=_INPUT, insertDataOption="INSERT_ROWS", body=body
        ).execute(num_retries=0)
        return
    number, by_channel = match
    if not status_only:
        values.update(
            spreadsheetId=spreadsheet_id, range=f"Sheet1!A{number}:F{number}", valueInputOption=_INPUT, body=body
        ).execute()
        return
    data: list[ValueRange] = [{"range": f"Sheet1!D{number}", "values": [[row[3]]]}]
    if by_channel:
        data.append({"range": f"Sheet1!F{number}", "values": [[incident.id]]})
    values.batchUpdate(spreadsheetId=spreadsheet_id, body={"valueInputOption": _INPUT, "data": data}).execute()


class GoogleSheetsIncidentListProjection:
    """``IncidentListProjection`` on the list spreadsheet named by ``[incident_core] list_sheet_id``."""

    async def append_row(self, incident: Incident) -> OperationResult[None]:
        """Write the incident's full row, in place when it has one, else appended."""
        return await self._upsert("append_row", incident, status_only=False)

    async def update_status(self, incident: Incident, status: IncidentStatus) -> OperationResult[None]:
        """Set the Status cell of the incident's row; with no row, append the full row carrying ``status``."""
        return await self._upsert("update_status", dataclasses.replace(incident, status=status), status_only=True)

    async def _upsert(self, operation: str, incident: Incident, *, status_only: bool) -> OperationResult[None]:
        spreadsheet_id = get_incident_core_settings().list_sheet_id
        if not spreadsheet_id:
            return OperationResult.permanent_error(
                "incident_core.list_sheet_id is not configured", ErrorCode.CONFIG_NOT_CONFIGURED
            )
        if get_google_workspace_settings().tenant is None:
            return OperationResult.permanent_error("google_workspace.tenant is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)
        conversation = incident.conversation
        if conversation is not None and conversation.system is not WorkplaceSystem.SLACK:
            return OperationResult.permanent_error(
                f"The incident list cannot link a conversation on {conversation.system.value}", ErrorCode.UNSUPPORTED_OPERATION
            )
        row = list_row(
            incident,
            channel_link=slack_conversation_link(conversation) if conversation is not None else None,
            channel_label=slack_conversation_label(incident) if conversation is not None else None,
        )
        try:
            await asyncio.to_thread(_write_row, spreadsheet_id, incident, row, status_only=status_only)
        except (HttpError, GoogleCredentialsRefused) as exc:
            if isinstance(exc, HttpError) and exc.resp.status == 400 and _UNPARSABLE_RANGE in str(exc):
                logger.warning("incident_list_projection_failed", operation=operation, error_code=ErrorCode.RANGE_NOT_FOUND)
                return OperationResult.error(
                    status=OperationStatus.NOT_FOUND,
                    message="The incident list has no Sheet1 tab",
                    error_code=ErrorCode.RANGE_NOT_FOUND,
                )
            status, error_code, retry_after = classify_google_error(exc)
            logger.warning(
                "incident_list_projection_failed",
                operation=operation,
                status=status.value,
                error_code=error_code,
                retry_after=retry_after,
            )
            return OperationResult.error(
                status=status, message=_failure_message(exc), error_code=error_code, retry_after=retry_after
            )
        return OperationResult.success(None)


def _failure_message(exc: HttpError | GoogleCredentialsRefused) -> str:
    """Name the failure without the request: an ``HttpError`` text carries the request url, which holds the sheet id."""
    return f"Google Sheets request failed: {exc.resp.status}" if isinstance(exc, HttpError) else str(exc)
