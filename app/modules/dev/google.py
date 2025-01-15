"""Testing new google service (will be removed)"""

from datetime import datetime
import os

from integrations.google_workspace import (
    google_directory,
)
from integrations.google_next.directory import GoogleDirectory

from dotenv import load_dotenv

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")


def get_members(group):
    members = google_directory.list_group_members(group)
    return members


def google_service_command(ack, client, body, respond, logger):
    ack()
    scopes = [
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
    ]
    g_directory = GoogleDirectory(scopes=scopes)
    query = "email:aws-*"
    start_next = datetime.now()
    groups_next = g_directory.list_groups_with_members(query=query)
    end_next = datetime.now()
    time_next = end_next - start_next
    logger.info(f"Google Next API call took {time_next} to complete")
    errors_next = any([group.get("error") for group in groups_next])
    start = datetime.now()
    groups = google_directory.list_groups_with_members(query=query)
    end = datetime.now()
    time = end - start
    logger.info(f"Google Workspace API call took {time} to complete")
    errors = any([group.get("error") for group in groups])
    if groups and groups_next:
        response_string = ""
        response_string += f"Google Workspace API call took {time.total_seconds():.2f} to complete and found {len(groups)} groups (errors? {errors})\n"
        response_string += f"Google Next API call took {time_next.total_seconds():.2f} to complete and found {len(groups_next)} groups (errors? {errors_next})"
        respond(response_string)
    else:
        respond("Nothing to see here.")
