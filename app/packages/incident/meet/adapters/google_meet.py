from typing import TYPE_CHECKING, cast

import structlog
from googleapiclient.errors import HttpError

from integrations.google_workspace.client import classify_google_error, get_meet_service

if TYPE_CHECKING:
    from googleapiclient._apis.meet.v2 import Space  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()
MEET_SCOPES = ["https://www.googleapis.com/auth/meetings.space.created"]


def create_space(**kwargs) -> dict:
    """Create a Google Meet space and return the API response payload."""
    config = {"accessType": "TRUSTED", "entryPointAccess": "ALL"}
    service = get_meet_service(
        scopes=MEET_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body = cast("Space", {"config": config})
    try:
        return service.spaces().create(body=body).execute()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise
