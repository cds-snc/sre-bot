from slack_sdk import WebClient
from slack_bolt import Respond
from integrations.google_workspace import google_docs
from modules.incident import incident_document, incident_folder, db_operations
from core.logging import get_module_logger

logger = get_module_logger()


def update_status(
    client: WebClient,
    respond: Respond,
    status: str,
    channel_id: str,
    channel_name: str,
    user_id: str,
    incident_id: str | None = None,
):

    document_id = ""
    try:
        response = client.bookmarks_list(channel_id=channel_id)
        if response["ok"]:
            for item in range(len(response["bookmarks"])):
                if response["bookmarks"][item]["title"] == "Incident report":
                    document_id = google_docs.extract_google_doc_id(
                        response["bookmarks"][item]["link"]
                    )
    except Exception as e:
        logger.warning(
            "incident_channel_bookmarks_not_found",
            channel=channel_name,
            error=str(e),
        )
        warning_message = f"Could not get bookmarks for channel {channel_name}: {e}"
        respond(warning_message)

    if document_id != "":
        try:
            incident_document.update_incident_document_status(document_id, status)
        except Exception as e:
            logger.warning(
                "incident_document_status_update_failed",
                channel=channel_name,
                error=str(e),
            )
            warning_message = f"Could not update the incident status in the document for channel {channel_name}: {e}"
            respond(warning_message)
    else:
        logger.warning(
            "incident_document_bookmark_not_found",
            channel=channel_name,
        )
        warning_message = f"No bookmark link for the incident document found for channel {channel_name}"
        respond(warning_message)

    try:
        incident_folder.update_spreadsheet_incident_status(
            incident_folder.return_channel_name(channel_name), status
        )
        if incident_id:
            db_operations.update_incident_field(incident_id, "status", status, user_id)
    except Exception as e:
        logger.warning(
            "incident_folder_status_update_failed",
            channel=channel_name,
            error=str(e),
        )
        warning_message = f"Could not update the incident status in the spreadsheet for channel {channel_name}: {e}"
        respond(warning_message)

    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has updated the incident status to {status}.",
        )
    except Exception as e:
        logger.warning(
            "incident_status_update_post_failed",
            channel=channel_name,
            error=str(e),
        )
        warning_message = f"Could not post the incident status update to the channel {channel_name}: {e}"
        respond(warning_message)
