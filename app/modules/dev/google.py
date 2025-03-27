"""Testing new google service (will be removed)"""

from core.config import settings
from integrations.google_workspace import (
    google_directory,
)


SRE_DRIVE_ID = settings.google_workspace.SRE_DRIVE_ID
SRE_INCIDENT_FOLDER = settings.google_workspace.SRE_INCIDENT_FOLDER
INCIDENT_TEMPLATE = settings.google_workspace.INCIDENT_TEMPLATE


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
