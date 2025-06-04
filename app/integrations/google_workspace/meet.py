"""Google Meet API integration module."""

from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
)


@handle_google_api_errors
def create_space(**kwargs) -> dict:
    """Creates a new and empty space in Google Meet.

    Args:
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Meet API containing the space details.
    """
    config = {"accessType": "TRUSTED", "entryPointAccess": "ALL"}
    return execute_google_api_call(
        "meet",
        "v2",
        "spaces",
        "create",
        scopes=["https://www.googleapis.com/auth/meetings.space.created"],
        body={"config": config},
        **kwargs,
    )
