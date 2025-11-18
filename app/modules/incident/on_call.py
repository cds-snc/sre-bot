"""Manage on call users"""

from slack_sdk import WebClient
from integrations.opsgenie import get_on_call_users
from modules.incident.incident_folder import get_folder_metadata


def get_on_call_users_from_folder(client: WebClient, folder: str) -> list:
    """Get the on call users for a given folder

    Args:
        client (WebClient): Slack WebClient
        folder (str): Google Drive folder ID
    Returns:
        list: List of on call users. If users are found, they will be Slack user objects.
    """
    oncall = []
    folder_metadata = get_folder_metadata(folder)
    if isinstance(folder_metadata, dict):
        folder_metadata = folder_metadata.get("appProperties", {})
    elif isinstance(folder_metadata, tuple) and len(folder_metadata) > 0:
        folder_metadata = folder_metadata[0].get("appProperties", {})
    else:
        folder_metadata = {}

    # Get OpsGenie data
    if "genie_schedule" in folder_metadata:
        for email in get_on_call_users(folder_metadata["genie_schedule"]):
            r = client.users_lookupByEmail(email=email)
            if r.get("ok"):
                oncall.append(r["user"])
    return oncall
