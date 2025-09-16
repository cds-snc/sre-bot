"""Core module to handle Incident creation"""

from slack_sdk import WebClient

from core.config import settings
from core.logging import get_module_logger
from integrations.google_workspace import meet
from models.incidents import IncidentPayload
from modules.incident import (
    incident_document,
    incident_folder,
    db_operations,
    on_call,
)

PREFIX = settings.PREFIX
INCIDENT_CHANNEL = settings.feat_incident.INCIDENT_CHANNEL
SLACK_SECURITY_USER_GROUP_ID = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID
INCIDENT_HANDBOOK_URL = settings.feat_incident.INCIDENT_HANDBOOK_URL

logger = get_module_logger()


def initiate_resources_creation(
    client: WebClient,
    incident_payload: IncidentPayload,
):
    """Create an incident and its related resources. If incident Slack channel provided, skips that resource creation"""

    # Create channel
    environment = "dev" if PREFIX == "dev-" else "prod"

    oncall = on_call.get_on_call_users_from_folder(client, incident_payload.folder)

    channel_url = f"https://gcdigital.slack.com/archives/{incident_payload.channel_id}"

    # Set topic
    client.conversations_setTopic(
        channel=incident_payload.channel_id,
        topic=f"Incident: {incident_payload.name} / {incident_payload.product}",
    )

    # Set the description
    client.conversations_setPurpose(
        channel=incident_payload.channel_id, purpose=f"{incident_payload.name}"
    )

    # Announce incident
    text = (
        f"<@{incident_payload.user_id}> has kicked off a new incident: {incident_payload.name} for {incident_payload.product}"
        f" in <#{incident_payload.channel_id}>\n"
        f"<@{incident_payload.user_id}> a initié un nouvel incident: {incident_payload.name} pour {incident_payload.product}"
        f" dans <#{incident_payload.channel_id}>"
    )
    if INCIDENT_CHANNEL:
        client.chat_postMessage(text=text, channel=INCIDENT_CHANNEL)

    # Add incident creator to channel
    client.conversations_invite(
        channel=incident_payload.channel_id, users=incident_payload.user_id
    )

    # Add meeting link
    meet_link = meet.create_space()
    client.bookmarks_add(
        channel_id=incident_payload.channel_id,
        title="Meet link",
        type="link",
        link=meet_link["meetingUri"],
    )

    # Create a canvas for the channel
    client.conversations_canvases_create(
        channel_id=incident_payload.channel_id,
        document_content={
            "type": "markdown",
            "markdown": "# Incident Canvas 📋\n\nUse this area to write/store anything you want. All you need to do is to start typing below!️",
        },
    )

    text = f"A hangout has been created at: {meet_link['meetingUri']}"
    client.chat_postMessage(text=text, channel=incident_payload.channel_id)

    # Create incident document
    document_id = incident_document.create_incident_document(
        incident_payload.slug, incident_payload.folder
    )
    logger.info("incident_document_created", document_id=document_id)

    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    incident_folder.add_new_incident_to_list(
        document_link,
        incident_payload.name,
        incident_payload.slug,
        incident_payload.product,
        channel_url,
    )

    folders = incident_folder.list_incident_folders()
    team_name = "Unknown"
    for f in folders:
        if f["id"] == incident_payload.folder:
            team_name = f["name"]
            break

    incident_data = {
        "channel_id": incident_payload.channel_id,
        "channel_name": incident_payload.channel_name,
        "name": incident_payload.name,
        "user_id": incident_payload.user_id,
        "teams": [team_name],
        "report_url": document_link,
        "meet_url": meet_link["meetingUri"],
        "environment": environment,
    }
    incident_id = db_operations.create_incident(incident_data)
    logger.info("incident_record_created", incident_id=incident_id)

    # Bookmark incident document
    client.bookmarks_add(
        channel_id=incident_payload.channel_id,
        title="Incident report",
        type="link",
        link=document_link,
    )

    text = f":lapage: An incident report has been created at: {document_link}"
    client.chat_postMessage(text=text, channel=incident_payload.channel_id)

    # Gather all user IDs in a list to ensure uniqueness
    users_to_invite = []

    # Add oncall users, excluding the user_id
    for user in oncall:
        if user["id"] != incident_payload.user_id:
            users_to_invite.append(user["id"])

    # Get users from the @security group
    if incident_payload.security_incident == "yes":
        # If this is a security incident, get users from the security user group
        # and add them to the list of users to invite
        response = client.usergroups_users_list(usergroup=SLACK_SECURITY_USER_GROUP_ID)

        # if we are testing, ie PREFIX is "dev" then don't add the security group users since we don't want to spam them
        if response.get("ok") and PREFIX == "":
            for security_user in response["users"]:
                if security_user != incident_payload.user_id:
                    users_to_invite.append(security_user)

    # Invite all collected users to the channel in a single API call
    if users_to_invite:
        client.conversations_invite(
            channel=incident_payload.channel_id, users=users_to_invite
        )
    text = """🚨 *Incident Resources Created Successfully!*
*Next Steps - Available Commands:*
• `/sre incident roles manage` - Assign roles to the incident
• `/sre incident schedule retro` - Schedule a retrospective meeting
• `/sre incident close` - Close and archive this incident
• `/sre incident status update <status>` - Update incident status
• `/sre incident updates add` - Add incident updates
• `/sre incident show` - View incident details

*Quick Actions:*
📋 Use the bookmarked incident report above to document findings
👥 Assign roles to team members for clear responsibilities
📅 Schedule a retro meeting when ready

_Type_ `/sre incident help` _for complete command list_"""
    client.chat_postMessage(text=text, channel=incident_payload.channel_id)
    incident_document.update_boilerplate_text(
        document_id,
        incident_payload.name,
        incident_payload.product,
        channel_url,
        ", ".join(list(map(lambda x: x["profile"]["display_name_normalized"], oncall))),
    )
    logger.info(
        "incident_successfully_created",
        incident_id=incident_id,
    )
