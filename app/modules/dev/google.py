"""Testing new google service (will be removed)"""
import os

from integrations.google_workspace import (
    google_directory,
)

from dotenv import load_dotenv

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")
REPORT_GOOGLE_GROUPS_FOLDER = "18IYoyg5AFz3ZsZSSqvP1iaJur1V3Fmvi"
GROUPS_MEMBERSHIPS_FOLDER = "1KPwrP-fWA0VVCrxW22Z4GJLcTb5-Avjf"


def get_members(group):
    members = google_directory.list_group_members(group)
    return members


def google_service_command(ack, client, body, respond, logger):
    ack()
    respond("Nothing to see here.")


def test_content():
    post_content = """
        This is a test post content.
        It can support multiple lines.

        For now, it is just a simple string. Future versions will support more complex content.

        Like HTML and markdown.
    """
    return post_content
