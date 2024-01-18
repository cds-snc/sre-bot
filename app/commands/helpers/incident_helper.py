import json
import re
import logging
from integrations import google_drive
from commands.utils import get_stale_channels, log_to_sentinel

help_text = """
\n `/sre incident create-folder <folder_name>`
\n      - create a folder for a team in the incident drive
\n      - créer un dossier pour une équipe dans le dossier d'incidents
\n `/sre incident help`
\n      - show this help text
\n      - afficher ce texte d'aide
\n `/sre incident list-folders`
\n      - list all folders in the incident drive
\n      - lister tous les dossiers dans le dossier d'incidents
\n `/sre incident roles`
\n      - manages roles in an incident channel
\n      - gérer les rôles dans un canal d'incident
\n `/sre incident close`
\n      - close the incident, archive the channel and update the incident spreadsheet and document
\n      - clôturer l'incident, archiver le canal et mettre à jour la feuille de calcul et le document de l'incident
\n `/sre incident stale`
\n      - lists all incidents older than 14 days with no activity
\n      - lister tous les incidents plus vieux que 14 jours sans activité
"""


def handle_incident_command(args, client, body, respond, ack):
    if len(args) == 0:
        respond(help_text)
        return

    action, *args = args
    match action:
        case "create-folder":
            name = " ".join(args)
            respond(google_drive.create_folder(name))
        case "help":
            respond(help_text)
        case "list-folders":
            list_folders(client, body, ack)
        case "roles":
            manage_roles(client, body, ack, respond)
        case "close":
            close_incident(client, body, ack)
        case "stale":
            stale_incidents(client, body, ack)
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )


def add_folder_metadata(client, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    blocks = {
        "type": "modal",
        "callback_id": "add_metadata_view",
        "title": {"type": "plain_text", "text": "SRE - Add metadata"},
        "submit": {"type": "plain_text", "text": "Save metadata"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": folder_id,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Add metadata*",
                },
            },
            {
                "type": "input",
                "block_id": "key",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "key",
                    "placeholder": {"type": "plain_text", "text": "Key"},
                },
                "label": {
                    "type": "plain_text",
                    "text": "Key",
                },
            },
            {
                "type": "input",
                "block_id": "value",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "value",
                    "placeholder": {"type": "plain_text", "text": "Value"},
                },
                "label": {
                    "type": "plain_text",
                    "text": "Value",
                },
            },
        ],
    }
    client.views_update(
        view_id=body["view"]["id"],
        view=blocks,
    )


def archive_channel_action(client, body, ack):
    ack()
    channel_id = body["channel"]["id"]
    action = body["actions"][0]["value"]
    user = body["user"]["id"]
    if action == "ignore":
        msg = f"<@{user}> has delayed archiving this channel for 14 days."
        client.chat_update(
            channel=channel_id, text=msg, ts=body["message_ts"], attachments=[]
        )
        log_to_sentinel("incident_channel_archive_delayed", body)
    elif action == "archive":
        # get the current chanel id and name and make up the body with those 2 values
        channel_info = {
            "channel_id": channel_id,
            "channel_name": body["channel"]["name"],
        }
        # Call the close_incident function to update the incident document to closed, update the spreadsheet and archive the channel
        close_incident(client, channel_info, ack)
        # log the event to sentinel
        log_to_sentinel("incident_channel_archived", body)


def delete_folder_metadata(client, body, ack):
    ack()
    folder_id = body["view"]["private_metadata"]
    key = body["actions"][0]["value"]
    google_drive.delete_metadata(folder_id, key)
    body["actions"] = [{"value": folder_id}]
    view_folder_metadata(client, body, ack)


def list_folders(client, body, ack):
    ack()
    folders = google_drive.list_folders()
    folders.sort(key=lambda x: x["name"])
    blocks = {
        "type": "modal",
        "callback_id": "list_folders_view",
        "title": {"type": "plain_text", "text": "SRE - Listing folders"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            item for sublist in list(map(folder_item, folders)) for item in sublist
        ],
    }
    client.views_open(trigger_id=body["trigger_id"], view=blocks)


def manage_roles(client, body, ack, respond):
    ack()
    channel_name = body["channel_name"]
    channel_name = channel_name[
        channel_name.startswith("incident-") and len("incident-") :
    ]
    documents = google_drive.get_document_by_channel_name(channel_name)

    if len(documents) == 0:
        respond(
            f"No incident document found for `{channel_name}`. Please make sure the channel matches the document name."
        )
        return

    document = documents[0]
    current_ic = (
        document["appProperties"]["ic_id"]
        if "appProperties" in document and "ic_id" in document["appProperties"]
        else False
    )
    current_ol = (
        document["appProperties"]["ol_id"]
        if "appProperties" in document and "ol_id" in document["appProperties"]
        else False
    )

    ic_element = {
        "type": "users_select",
        "placeholder": {
            "type": "plain_text",
            "text": "Select an incident commander",
        },
        "action_id": "ic_select",
    }
    if current_ic:
        ic_element["initial_user"] = current_ic

    ol_element = {
        "type": "users_select",
        "placeholder": {
            "type": "plain_text",
            "text": "Select an operations lead",
        },
        "action_id": "ol_select",
    }
    if current_ol:
        ol_element["initial_user"] = current_ol

    blocks = {
        "type": "modal",
        "callback_id": "view_save_incident_roles",
        "title": {"type": "plain_text", "text": "SRE - Roles management"},
        "submit": {"type": "plain_text", "text": "Save roles"},
        "private_metadata": json.dumps(
            {
                "id": document["id"],
                "ic_id": current_ic,
                "ol_id": current_ol,
                "channel_id": body["channel_id"],
            }
        ),
        "blocks": (
            [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Roles for {channel_name}",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "ic_name",
                    "element": ic_element,
                    "label": {
                        "type": "plain_text",
                        "text": "Incident Commander",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "ol_name",
                    "element": ol_element,
                    "label": {
                        "type": "plain_text",
                        "text": "Operations Lead",
                    },
                },
            ]
        ),
    }
    client.views_open(trigger_id=body["trigger_id"], view=blocks)


def save_metadata(client, body, ack, view):
    ack()
    folder_id = view["private_metadata"]
    key = view["state"]["values"]["key"]["key"]["value"]
    value = view["state"]["values"]["value"]["value"]["value"]
    google_drive.add_metadata(folder_id, key, value)
    body["actions"] = [{"value": folder_id}]
    del body["view"]
    view_folder_metadata(client, body, ack)


def save_incident_roles(client, ack, view):
    ack()
    selected_ic = view["state"]["values"]["ic_name"]["ic_select"]["selected_user"]
    selected_ol = view["state"]["values"]["ol_name"]["ol_select"]["selected_user"]
    metadata = json.loads(view["private_metadata"])
    file_id = metadata["id"]
    google_drive.add_metadata(file_id, "ic_id", selected_ic)
    google_drive.add_metadata(file_id, "ol_id", selected_ol)
    if metadata["ic_id"] != selected_ic:
        client.chat_postMessage(
            text=f"<@{selected_ic}> has been assigned as incident commander for this incident.",
            channel=metadata["channel_id"],
        )
    if metadata["ol_id"] != selected_ol:
        client.chat_postMessage(
            text=f"<@{selected_ol}> has been assigned as operations lead for this incident.",
            channel=metadata["channel_id"],
        )
    client.conversations_setTopic(
        topic=f"IC: <@{selected_ic}> / OL: <@{selected_ol}>",
        channel=metadata["channel_id"],
    )


def close_incident(client, body, ack):
    ack()
    # get the current chanel id and name
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]

    if not channel_name.startswith("incident-"): 
        user_id = body["user_id"]
        client.chat_postEphemeral(
            text = f"Channel {channel_name} is not an incident channel. Please use the command in an incident channel.",
            channel=channel_id,
            user = user_id
        )
        return 

    # get and update the incident document
    document_id = ""
    response = client.bookmarks_list(channel_id=channel_id)
    if response["ok"]:
        for item in range(len(response["bookmarks"])):
            if response["bookmarks"][item]["title"] == "Incident report":
                document_id = extract_google_doc_id(response["bookmarks"][item]["link"])

    # Update the document status to "Closed" if we can get the document
    if document_id != "":
        google_drive.close_incident_document(document_id)
    else:
        logging.warning("No incident document found for this channel.")

    # Update the spreadsheet with the current incident with status = closed
    google_drive.update_spreadsheet_close_incident(return_channel_name(channel_name))

    # archive the channel
    client.conversations_archive(channel=channel_id)


def stale_incidents(client, body, ack):
    ack()

    placeholder = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Loading stale incident list ...(this may take a minute)",
                },
            }
        ],
    }

    placeholder_modal = client.views_open(
        trigger_id=body["trigger_id"], view=placeholder
    )

    stale_channels = get_stale_channels(client)

    blocks = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            item
            for sublist in list(map(channel_item, stale_channels))
            for item in sublist
        ],
    }

    client.views_update(view_id=placeholder_modal["view"]["id"], view=blocks)


def view_folder_metadata(client, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    folder = google_drive.list_metadata(folder_id)
    blocks = {
        "type": "modal",
        "callback_id": "view_folder_metadata_modal",
        "title": {"type": "plain_text", "text": "SRE - Showing metadata"},
        "submit": {"type": "plain_text", "text": "Return to folders"},
        "private_metadata": folder_id,
        "blocks": (
            [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": folder["name"],
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Add metadata"},
                        "value": folder_id,
                        "action_id": "add_folder_metadata",
                    },
                },
                {"type": "divider"},
            ]
            + metadata_items(folder)
        ),
    }
    if "view" in body:
        client.views_update(
            view_id=body["view"]["id"],
            view=blocks,
        )
    else:
        client.views_open(trigger_id=body["trigger_id"], view=blocks)


def channel_item(channel):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<#{channel['id']}>",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": channel["topic"]["value"]
                    if channel["topic"]["value"]
                    else "No information available",
                }
            ],
        },
        {"type": "divider"},
    ]


def folder_item(folder):
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{folder['name']}*"},
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Manage metadata",
                    "emoji": True,
                },
                "value": f"{folder['id']}",
                "action_id": "view_folder_metadata",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<https://drive.google.com/drive/u/0/folders/{folder['id']}|View in Google Drive>",
                }
            ],
        },
        {"type": "divider"},
    ]


def metadata_items(folder):
    if "appProperties" not in folder or len(folder["appProperties"]) == 0:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*No metadata found. Click the button above to add metadata.*",
                },
            },
        ]
    else:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{key}*\n{value}",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete metadata",
                        "emoji": True,
                    },
                    "value": key,
                    "style": "danger",
                    "action_id": "delete_folder_metadata",
                },
            }
            for key, value in folder["appProperties"].items()
        ]


def extract_google_doc_id(url):
    # Regular expression pattern to match Google Docs ID
    pattern = r"/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None


def return_channel_name(input_str):
    # return the channel name without the incident- prefix and appending a # to the channel name
    prefix = "incident-"
    if input_str.startswith(prefix):
        return "#" + input_str[len(prefix) :]
    return input_str
