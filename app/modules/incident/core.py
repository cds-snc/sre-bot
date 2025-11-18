"""Core module to handle Incident creation"""

from slack_sdk import WebClient

from core.config import settings
from core.logging import get_module_logger
from integrations.google_workspace import meet, google_drive
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


def recreate_missing_resources(
    client: WebClient,
    channel_id: str,
    channel_name: str,
    user_id: str,
):
    """
    Detect and recreate missing incident resources for an existing incident channel.

    This function checks for missing resources (bookmarks, incident list entry, DB record)
    and attempts to create only what's missing.

    Args:
        client: Slack WebClient instance
        channel_id: The incident channel ID
        channel_name: The incident channel name (e.g., 'incident-2024-001')
        user_id: The user requesting the resource recreation

    Returns:
        dict: Summary of actions taken and any errors encountered
    """
    results = {
        "success": [],
        "errors": [],
        "skipped": [],
    }

    # Get basic channel info
    try:
        channel_info = client.conversations_info(channel=channel_id)
        if not channel_info.get("ok"):
            results["errors"].append("Failed to fetch channel information")
            return results

        channel = channel_info["channel"]
        topic = channel.get("topic", {}).get("value", "Placeholder / Site reliability engineering")

        # Parse incident name and product from topic
        # Expected format: "Incident: {name} / {product}"
        incident_name = ""
        product = ""
        if topic and " / " in topic:
            parts = topic.split(" / ")
            if len(parts) >= 2:
                incident_name = parts[0].replace("Incident: ", "").strip()
                product = parts[1].strip()

        if not incident_name:
            incident_name = channel_name.replace("incident-", "").replace("dev-", "")

        if not product:
            product = "Unknown"

    except Exception as e:
        logger.error(
            "recreate_missing_resources_channel_info_failed",
            channel_id=channel_id,
            error=str(e),
        )
        results["errors"].append(f"Failed to get channel info: {str(e)}")
        return results

    # Check for existing bookmarks
    existing_bookmarks = {}
    try:
        bookmark_response = client.bookmarks_list(channel_id=channel_id)
        if bookmark_response.get("ok"):
            for bookmark in bookmark_response.get("bookmarks", []):
                existing_bookmarks[bookmark["title"]] = bookmark["link"]
    except Exception as e:
        logger.warning(
            "recreate_missing_resources_bookmark_check_failed",
            channel_id=channel_id,
            error=str(e),
        )

    # Check if incident exists in database
    incident_record = db_operations.get_incident_by_channel_id(channel_id)

    # Try to determine the product folder
    folder_id = None
    if product != "Unknown":
        folders = incident_folder.list_incident_folders()
        for folder in folders:
            if folder["name"].lower() == product.lower():
                folder_id = folder["id"]
                break

    # 1. Check/Create Meet link bookmark
    if "Meet link" not in existing_bookmarks:
        try:
            meet_link = meet.create_space()
            client.bookmarks_add(
                channel_id=channel_id,
                title="Meet link",
                type="link",
                link=meet_link["meetingUri"],
            )
            results["success"].append(f"Created Meet link: {meet_link['meetingUri']}")
            logger.info(
                "recreate_missing_resources_meet_created",
                channel_id=channel_id,
                meet_url=meet_link["meetingUri"],
            )
        except Exception as e:
            logger.error(
                "recreate_missing_resources_meet_failed",
                channel_id=channel_id,
                error=str(e),
            )
            results["errors"].append(f"Failed to create Meet link: {str(e)}")
    else:
        results["skipped"].append("Meet link bookmark already exists")

    # 2. Check/Create Incident report bookmark
    document_id = None
    document_link = None

    if "Incident report" not in existing_bookmarks:
        # Try to find existing document in the folder
        if folder_id:
            try:
                # Search for document by name in the folder
                slug = channel_name.replace("incident-", "")

                # Check if document already exists
                files = google_drive.list_files_in_folder(folder_id)
                for file in files:
                    if slug in file.get("name", ""):
                        document_id = file["id"]
                        document_link = (
                            f"https://docs.google.com/document/d/{document_id}/edit"
                        )
                        break

                # If no existing document found, create one
                if not document_id:
                    document_id = incident_document.create_incident_document(
                        slug, folder_id
                    )
                    document_link = (
                        f"https://docs.google.com/document/d/{document_id}/edit"
                    )

                    # Update boilerplate if we have the necessary info
                    channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"
                    oncall = on_call.get_on_call_users_from_folder(client, folder_id)
                    oncall_names = ", ".join(
                        [user["profile"]["display_name_normalized"] for user in oncall]
                    )

                    incident_document.update_boilerplate_text(
                        document_id,
                        incident_name,
                        product,
                        channel_url,
                        oncall_names,
                    )
                    results["success"].append(
                        f"Created incident document: {document_link}"
                    )
                else:
                    results["success"].append(
                        f"Found existing document: {document_link}"
                    )

                # Add bookmark
                client.bookmarks_add(
                    channel_id=channel_id,
                    title="Incident report",
                    type="link",
                    link=document_link,
                )
                results["success"].append("Added Incident report bookmark")

                logger.info(
                    "recreate_missing_resources_document_bookmarked",
                    channel_id=channel_id,
                    document_id=document_id,
                )

            except Exception as e:
                logger.error(
                    "recreate_missing_resources_document_failed",
                    channel_id=channel_id,
                    error=str(e),
                )
                results["errors"].append(
                    f"Failed to create/bookmark incident document: {str(e)}"
                )
        else:
            results["errors"].append(
                "Cannot create incident document: product folder not found"
            )
    else:
        document_link = existing_bookmarks["Incident report"]
        results["skipped"].append("Incident report bookmark already exists")

    # 3. Check/Add incident to Google Sheets list
    if document_link:
        try:
            # Check if incident already exists in the list
            incidents_in_sheet = incident_folder.get_incidents_from_sheet()
            slug = channel_name.replace("incident-", "")

            already_in_sheet = False
            for inc in incidents_in_sheet:
                if inc.get("channel_id") == channel_id or slug in inc.get(
                    "channel_name", ""
                ):
                    already_in_sheet = True
                    break

            if not already_in_sheet:
                channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"
                incident_folder.add_new_incident_to_list(
                    document_link,
                    incident_name,
                    slug,
                    product,
                    channel_url,
                )
                results["success"].append("Added incident to Google Sheets list")
                logger.info(
                    "recreate_missing_resources_sheet_updated",
                    channel_id=channel_id,
                    incident_name=incident_name,
                )
            else:
                results["skipped"].append(
                    "Incident already exists in Google Sheets list"
                )

        except Exception as e:
            logger.error(
                "recreate_missing_resources_sheet_failed",
                channel_id=channel_id,
                error=str(e),
            )
            results["errors"].append(
                f"Failed to add incident to Google Sheets: {str(e)}"
            )

    # 4. Check/Create database record
    if not incident_record:
        try:
            environment = "dev" if PREFIX == "dev-" else "prod"
            meet_url = existing_bookmarks.get("Meet link", "")

            incident_data = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "name": incident_name,
                "user_id": user_id,
                "teams": [product],
                "report_url": document_link or "",
                "meet_url": meet_url,
                "environment": environment,
            }

            incident_id = db_operations.create_incident(incident_data)
            if incident_id:
                results["success"].append(f"Created database record: {incident_id}")
                logger.info(
                    "recreate_missing_resources_db_created",
                    channel_id=channel_id,
                    incident_id=incident_id,
                )
            else:
                results["errors"].append("Failed to create database record")

        except Exception as e:
            logger.error(
                "recreate_missing_resources_db_failed",
                channel_id=channel_id,
                error=str(e),
            )
            results["errors"].append(f"Failed to create database record: {str(e)}")
    else:
        results["skipped"].append("Database record already exists")

    return results


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
