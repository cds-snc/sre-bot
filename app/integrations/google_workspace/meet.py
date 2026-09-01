"""Google Meet API integration module."""

from typing import TYPE_CHECKING, cast

from integrations.google_workspace import client as google_service_client

if TYPE_CHECKING:
    from googleapiclient._apis.meet.v2 import Space  # pyright: ignore[reportMissingModuleSource]

MEET_SCOPES = ["https://www.googleapis.com/auth/meetings.space.created"]


def create_space(**kwargs) -> dict:
    """Creates a new and empty space in Google Meet.

    Args:
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Meet API containing the space details.
    """
    config = {"accessType": "TRUSTED", "entryPointAccess": "ALL"}
    service = google_service_client.get_meet_service(
        scopes=MEET_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body = cast("Space", {"config": config})
    result: dict = google_service_client.execute_google_api_request(service.spaces().create(body=body))
    return result
