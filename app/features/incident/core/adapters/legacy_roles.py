"""Legacy-only read of an incident's roles from its report document's Drive properties.

Before the roles moved to the incident record, ``/sre incident roles manage`` kept the
incident commander and the operations lead as the report's Drive ``appProperties``
``ic_id`` and ``ol_id``. This adapter reads them, and only reads: nothing writes those
properties any more. It is the read bridge for an incident whose record holds no role
yet, and is deleted with the legacy contract once the legacy upgrade job's backfill
reports nothing pending.

TODO(TASK-145.13): delete with ``LegacyRolesReader`` and ``read_incident_roles`` in ``core/api.py``.
"""

import asyncio
from collections.abc import Mapping

from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters import google_docs
from features.incident.core.domain import ReportReference
from integrations.google_workspace.client import classify_google_error

_PROPERTY_ROLES = (("ic_id", IncidentRole.INCIDENT_COMMANDER), ("ol_id", IncidentRole.OPERATIONS_LEAD))


class GoogleDriveLegacyRolesReader:
    """Read the legacy roles from the Drive properties of a Google report; the single blocking call runs in one thread."""

    async def read(self, report: ReportReference) -> OperationResult[Mapping[IncidentRole, str]]:
        """Return the commander and lead the report's Drive properties name, a blank or missing one left out.

        A report of another system is PERMANENT_ERROR with ``UNSUPPORTED_OPERATION`` without a call; a Drive
        failure is the classified result (a missing file is NOT_FOUND),
        already logged by the Drive call.
        """
        if report.system is not WorkplaceSystem.GOOGLE:
            return OperationResult.permanent_error(
                f"Google Drive cannot reach a report on {report.system.value}", ErrorCode.UNSUPPORTED_OPERATION
            )
        try:
            metadata = await asyncio.to_thread(google_docs.get_metadata, report.vendor_id, "appProperties")
        except HttpError as exc:
            status, error_code, retry_after = classify_google_error(exc)
            return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
        properties = metadata.get("appProperties") or {}
        roles = {role: holder for key, role in _PROPERTY_ROLES if (holder := str(properties.get(key) or "").strip())}
        return OperationResult.success(roles)
