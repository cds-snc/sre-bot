"""Testing new google service (will be removed)"""

import os

from integrations.google_workspace import gmail
from integrations.slack import users as slack_users

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


def google_service_command(ack, client, body, respond, logger):
    ack()
    post_content = test_content()
    user_id = slack_users.get_user_email_from_body(client, body)
    create_message = gmail.create_email_message(
        "Test ATI message", post_content, user_id, ""
    )

    response = gmail.create_draft(
        message=create_message,
        user_id=user_id,
        delegated_user_email=user_id,
    )

    logger.info(response)
    if not response:
        respond("No response")
    else:
        respond("Found users")


def test_content():
    post_content = """
        This is a test post content.
        It can support multiple lines.

        For now, it is just a simple string. Future versions will support more complex content.

        Like HTML and markdown.
    """
    return post_content
