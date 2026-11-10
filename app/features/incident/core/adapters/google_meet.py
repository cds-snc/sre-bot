"""Google Meet adapter of the incident core: the incident video call.

The only module in features/incident/ that reaches Google Meet.
``GoogleMeetVideoCall`` is the ``VideoCall`` behind ``core.api``: its ``create``
is async and runs the blocking Meet request through ``asyncio.to_thread``
inside the adapter (decisions/outbound-clients.md), bounded by the gateway's
per-attempt timeout with SDK retries off, and returns classified results.
``create_space`` is the legacy entry point the legacy declare and recreate call
until their cutovers delete it. No call takes a delegation subject.
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

import structlog
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem
from features.incident.core.domain import VideoCallReference
from integrations.google_workspace.client import GoogleCredentialsRefused, classify_google_error, get_meet_service
from integrations.google_workspace.settings import get_google_workspace_settings

if TYPE_CHECKING:
    from googleapiclient._apis.meet.v2 import Space  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()
MEET_SCOPES = ["https://www.googleapis.com/auth/meetings.space.created"]


def _create_space_request() -> dict[str, Any]:
    """Create a trusted-access Meet space; blocking, one attempt (Meet has no idempotency key for creation)."""
    service = get_meet_service(scopes=MEET_SCOPES)
    body = cast("Space", {"config": {"accessType": "TRUSTED", "entryPointAccess": "ALL"}})
    return cast("dict[str, Any]", service.spaces().create(body=body).execute(num_retries=0))


def create_space() -> dict[str, Any]:
    """Create a Google Meet space and return the API response payload (legacy callers)."""
    try:
        return _create_space_request()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise


class GoogleMeetVideoCall:
    """``VideoCall`` on Google Meet, naming each call under the configured Google tenant."""

    async def create(self) -> OperationResult[VideoCallReference]:
        """Create a Meet space off the event loop and return its reference, or a classified error."""
        tenant = get_google_workspace_settings().tenant
        if tenant is None:
            return OperationResult.permanent_error("google_workspace.tenant is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)
        try:
            payload = await asyncio.to_thread(_create_space_request)
        except (HttpError, GoogleCredentialsRefused) as exc:
            status, error_code, retry_after = classify_google_error(exc)
            logger.warning(
                "incident_video_call_create_failed",
                status=status.value,
                error_code=error_code,
                retry_after=retry_after,
            )
            return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
        name, url = payload.get("name"), payload.get("meetingUri")
        if not name or not url:
            logger.warning("incident_video_call_create_failed", reason="incomplete_space")
            return OperationResult.transient_error(message="The video call was created without a name or link")
        return OperationResult.success(
            VideoCallReference(system=WorkplaceSystem.GOOGLE, tenant=tenant.customer_id, vendor_id=name, url=url)
        )

    def link(self, call: VideoCallReference) -> str | None:
        """Return the stored link of a Google call; a call of another system has none here."""
        return call.url if call.system is WorkplaceSystem.GOOGLE else None
