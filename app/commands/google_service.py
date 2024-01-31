"""Testing new google service (will be removed)"""
import os

from integrations.google_workspace.google_service import get_google_service
from dotenv import load_dotenv

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")


def open_modal(client, body):
    folders = list_folders()
    folder_names = [i["name"] for i in folders]
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f"*{name}*"}} for name in folder_names]
    view = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": "Folder List"
        },
        "blocks": blocks
    }
    client.views_open(trigger_id=body["trigger_id"], view=view)


def google_service_command(client, body):
    open_modal(client, body)


def list_folders():
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .list(
            pageSize=25,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            q="parents in '{}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false and not name contains '{}'".format(
                SRE_INCIDENT_FOLDER, "Templates"
            ),
            driveId=SRE_DRIVE_ID,
            fields="nextPageToken, files(id, name)",
        )
        .execute()
    )
    return results.get("files", [])
