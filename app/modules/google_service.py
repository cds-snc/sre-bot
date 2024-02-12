"""Testing new google service (will be removed)"""
import os

from integrations.google_workspace import google_drive
from dotenv import load_dotenv

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")


def open_modal(client, body, folders):
    if not folders:
        return
    folder_names = [i["name"] for i in folders]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{name}*"}}
        for name in folder_names
    ]
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Folder List"},
        "blocks": blocks,
    }
    client.views_open(trigger_id=body["trigger_id"], view=view)


def google_service_command(client, body, respond):
    respond(f"Healthcheck status: {google_drive.healthcheck()}")
    folders = google_drive.list_folders_in_folder(SRE_INCIDENT_FOLDER)
    if not folders:
        respond("The folder ID is invalid. Please check the environment variables.")
        return
    open_modal(client, body, folders)
