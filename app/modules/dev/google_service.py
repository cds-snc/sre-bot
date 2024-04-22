"""Testing new google service (will be removed)"""
import os
import json
from datetime import datetime, timedelta, timezone
from integrations.google_workspace import (
    google_directory,
    google_drive,
    google_calendar,
)
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


def google_service_command(ack, client, body, respond):
    # ack()

    # folders = google_drive.list_folders_in_folder(SRE_INCIDENT_FOLDER)

    # if not folders:
    #     respond("The folder ID is invalid. Please check the environment variables.")
    #     return

    # respond(f"Found {len(folders)} folders.")

    # files = google_drive.list_files_in_folder(SRE_INCIDENT_FOLDER)

    # if not files:
    #     respond("The folder ID is invalid. Please check the environment variables.")
    #     return

    # respond(f"Found {len(files)} files.")

    # find_docs = google_drive.get_file_by_name('incidents', SRE_INCIDENT_FOLDER)
    # if not find_docs:
    #     respond("The folder ID is invalid. Please check the environment variables.")
    #     return

    # respond(f"Found {len(find_docs)} files.")
    items = [
        {"id": "guillaume.charest@cds-snc.ca"},
        {"id": "sylvia.mclaughlin@cds-snc.ca"},
    ]
    now = datetime.now(timezone.utc)
    days = 1
    # time_min is the current time + days and time_max is the current time + 60 days + days
    time_min = (now + timedelta(days=days)).isoformat()
    time_max = (now + timedelta(days=(60 + days))).isoformat()
    freebusy_results = google_calendar.get_freebusy(time_min, time_max, items)
    # respond(freebusy_results)
    first_available_start, first_available_end = google_calendar.find_first_available_slot(
        freebusy_results, days)
    respond(f"First available slot: {first_available_start} to {first_available_end}")

    # respond(f"Healthcheck status: {google_drive.healthcheck()}")
    # folders = google_drive.list_folders_in_folder(SRE_INCIDENT_FOLDER)
    # if not folders:
    #     respond("The folder ID is invalid. Please check the environment variables.")
    #     return
    # users = google_directory.list_users()
    # if not users:
    #     respond("There was an error retrieving the users.")
    #     return
    # respond(f"Found {len(users)} users.")
    # groups = google_directory.list_groups()
    # if not groups:
    #     respond("There was an error retrieving the groups.")
    #     return
    # respond(f"Found {len(groups)} groups.")
    # group_members = google_directory.list_group_members(groups[0]["id"])
    # if not group_members:
    #     respond("There was an error retrieving the group members.")
    #     return
    # respond(f"Found {len(group_members)} group members in group {groups[0]['name']}.")
