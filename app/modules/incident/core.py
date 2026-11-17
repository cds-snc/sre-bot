"""Core module to handle Incident creation"""

from urllib.parse import urlencode

from slack_sdk import WebClient
from slack_sdk.models import blocks
from structlog import get_logger

from contracts.configuration import host_info
from features.incident.core.adapters import google_meet as meet
from features.incident.response.settings import get_incident_response_settings
from integrations.slack.settings import get_slack_settings
from models.incidents import IncidentPayload
from modules.incident import (
    db_operations,
    incident_document,
    incident_folder,
    on_call,
)

logger = get_logger()


def channel_url(channel_id: str) -> str:
    """Link to a channel through Slack's deep link, naming the configured workspace when there is one."""
    tenant = get_slack_settings().tenant
    query = {"channel": channel_id} | ({"team": tenant.team_id} if tenant and tenant.team_id else {})
    return f"https://slack.com/app_redirect?{urlencode(query)}"


def _security_answer_to_flag(answer: str) -> bool | None:
    """Map the declare modal's yes/no answer to the stored flag; anything else is NULL."""
    return {"yes": True, "no": False}.get(answer)


def initiate_resources_creation(
    client: WebClient,
    incident_payload: IncidentPayload,
):
    """Create an incident and its related resources. If incident Slack channel provided, skips that resource creation"""
    incident_settings = get_incident_response_settings()

    # Create channel
    environment = "prod" if host_info().environment == "production" else "dev"

    oncall = on_call.get_on_call_users_from_folder(client, incident_payload.folder)

    channel_link = channel_url(incident_payload.channel_id)

    # Set topic
    client.conversations_setTopic(
        channel=incident_payload.channel_id,
        topic=f"Incident: {incident_payload.name} / {incident_payload.product}",
    )

    # Set the description
    client.conversations_setPurpose(channel=incident_payload.channel_id, purpose=f"{incident_payload.name}")

    # Announce incident
    text = (
        f"<@{incident_payload.user_id}> has kicked off a new incident: {incident_payload.name} for {incident_payload.product}"
        f" in <#{incident_payload.channel_id}>\n"
        f"<@{incident_payload.user_id}> a initié un nouvel incident: {incident_payload.name} pour {incident_payload.product}"
        f" dans <#{incident_payload.channel_id}>"
    )
    if incident_settings.announcement_channel_id:
        client.chat_postMessage(text=text, channel=incident_settings.announcement_channel_id)

    # Add incident creator to channel
    client.conversations_invite(channel=incident_payload.channel_id, users=incident_payload.user_id)

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

    if isinstance(incident_payload.severity, str) and incident_payload.severity.lower() in ["sev-1", "sev-2", "sev-3", "sev-4"]:
        warning_string = f"\n:rotating_light: *SEVERITY WARNING: {incident_payload.severity.upper()}*  :rotating_light: \n\n\n_The incident was initially called with a {incident_payload.severity.upper()} severity level._"
        message_blocks: list[blocks.SectionBlock | blocks.DividerBlock] = [
            blocks.DividerBlock(),
            blocks.SectionBlock(text=blocks.MarkdownTextObject(text=warning_string)),
            blocks.DividerBlock(),
        ]
        client.chat_postMessage(
            blocks=message_blocks,
            channel=incident_payload.channel_id,
        )

    text = f"A hangout has been created at: {meet_link['meetingUri']}"
    client.chat_postMessage(text=text, channel=incident_payload.channel_id)

    # Create incident document
    document_id = incident_document.create_incident_document(incident_payload.slug, incident_payload.folder)
    logger.info("incident_document_created", document_id=document_id)

    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    incident_folder.add_new_incident_to_list(
        document_link,
        incident_payload.name,
        incident_payload.slug,
        incident_payload.product,
        channel_link,
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
        "severity": incident_payload.severity,
        "security_incident": _security_answer_to_flag(incident_payload.security_incident),
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

    if incident_payload.source_alert_permalink:
        client.bookmarks_add(
            channel_id=incident_payload.channel_id,
            title="Source alert",
            type="link",
            link=incident_payload.source_alert_permalink,
        )
        client.chat_postMessage(
            text=f"Source alert: <{incident_payload.source_alert_permalink}|View original alert>",
            channel=incident_payload.channel_id,
        )

    # Gather all user IDs in a list to ensure uniqueness
    users_to_invite = []

    # Add oncall users, excluding the user_id
    for user in oncall:
        if user["id"] != incident_payload.user_id:
            users_to_invite.append(user["id"])

    # Get users from the @security group
    security_group_id = incident_settings.security_group_id
    if incident_payload.security_incident == "yes" and not security_group_id:
        logger.warning("security_user_group_not_configured", channel_id=incident_payload.channel_id)
    elif incident_payload.security_incident == "yes" and security_group_id:
        # If this is a security incident, get users from the security user group
        # and add them to the list of users to invite
        response = client.usergroups_users_list(usergroup=security_group_id)

        # Avoid inviting security group users outside production to prevent spam.
        if response.get("ok") and host_info().environment == "production":
            for security_user in response["users"]:
                if security_user != incident_payload.user_id:
                    users_to_invite.append(security_user)

    # Get users from the @incident-policy group
    policy_group_id = incident_settings.policy_group_id
    if incident_payload.policy_help == "yes" and not policy_group_id:
        logger.warning("policy_user_group_not_configured", channel_id=incident_payload.channel_id)
    elif incident_payload.policy_help == "yes":
        response = client.usergroups_users_list(usergroup=policy_group_id)

        # Avoid inviting policy group users outside production to prevent spam.
        if response.get("ok") and host_info().environment == "production":
            for policy_user in response["users"]:
                if policy_user != incident_payload.user_id and policy_user not in users_to_invite:
                    users_to_invite.append(policy_user)
        elif not response.get("ok"):
            logger.warning("policy_group_fetch_failed", error=response.get("error"), usergroup=policy_group_id)

    # Get users from the @notify-management group
    if incident_payload.product == "Notify" and incident_settings.notify_management_group_id:
        # If this is a Notify product incident, get users from the Notify management user group
        # and add them to the list of users to invite
        response = client.usergroups_users_list(usergroup=incident_settings.notify_management_group_id)
        if response.get("ok"):
            for notify_user in response["users"]:
                if notify_user != incident_payload.user_id:
                    users_to_invite.append(notify_user)
        else:
            logger.warning(
                "notify_mgmt_group_fetch_failed",
                error=response.get("error"),
                usergroup=incident_settings.notify_management_group_id,
            )

    # Invite all collected users to the channel in a single API call
    if users_to_invite:
        client.conversations_invite(channel=incident_payload.channel_id, users=users_to_invite)
    text = """🚨 *Incident Resources Created Successfully!*
*Next Steps - Available Commands:*
• `/sre incident roles manage` - Assign roles to the incident
• `/sre incident schedule retro` - Schedule a retrospective meeting
• `/sre incident close` - Close and archive this incident
• `/sre incident status update <status>` - Update incident status
• `/sre incident status-update` - Draft, review and approve a public status update
• `/sre incident show` - View incident details
• `/sre incident summarize` - Summarize the channel to catch up someone joining the incident (optionally add `--since 30m` or `--since 2h` to limit the time range)
• `/sre incident draft` - Draft an incident report from this channel into a new document, ready for you to review and edit

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
        channel_link,
        ", ".join([x["profile"]["display_name_normalized"] for x in oncall]),
    )
    logger.info(
        "incident_successfully_created",
        incident_id=incident_id,
    )
