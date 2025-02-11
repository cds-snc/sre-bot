import logging
from slack_sdk import WebClient
from slack_bolt import Respond
from integrations.google_workspace import google_docs
from modules.incident import incident_document, incident_folder, db_operations


def update_status(
    client: WebClient,
    respond: Respond,
    logger,
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
        warning_message = f"Could not get bookmarks for channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)

    if document_id != "":
        try:
            incident_document.update_incident_document_status(document_id, status)
        except Exception as e:
            warning_message = f"Could not update the incident status in the document for channel {channel_name}: {e}"
            logging.warning(warning_message)
            respond(warning_message)
    else:
        warning_message = f"No bookmark link for the incident document found for channel {channel_name}"
        logging.warning(warning_message)
        respond(warning_message)

    try:
        incident_folder.update_spreadsheet_incident_status(
            incident_folder.return_channel_name(channel_name), status
        )
        if incident_id:
            db_operations.update_incident_field(
                logger, incident_id, "status", status, user_id
            )
    except Exception as e:
        warning_message = f"Could not update the incident status in the spreadsheet for channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)

    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has updated the incident status to {status}.",
        )
    except Exception as e:
        warning_message = f"Could not post the incident status update to the channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)
