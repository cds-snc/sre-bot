"""Module for managing SRE incident folders in Google Drive.

Includes the folder metadata views and actions (the product's on-call schedule reference).
"""

from slack_bolt import Ack
from slack_sdk.web import WebClient
from structlog import get_logger

from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters import google_docs as incident_drive

logger = get_logger()

# Temporary TASK-25.1.6 shim for Slack's modal block and option-list limits.
LEGACY_FOLDER_DISPLAY_LIMIT = 25


def _folders_modal(blocks: list[dict]) -> dict:
    return {
        "type": "modal",
        "callback_id": "list_folders_view",
        "title": {"type": "plain_text", "text": "SRE - Listing folders"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks,
    }


def _text_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def list_folders_view(client: WebClient, body, ack: Ack):
    """Open a loading modal first, then fill it from Drive.

    The trigger_id expires 3 seconds after the command; a cold Drive read can outlast it,
    so the modal opens before the read and views_update fills it.
    """
    ack()
    opened = client.views_open(
        trigger_id=body["trigger_id"], view=_folders_modal([_text_block(":hourglass: Loading products...")])
    )
    view_id = opened["view"]["id"]
    try:
        folders = incident_drive.list_child_folders(get_incident_core_settings().folder_id)
    except Exception as error:
        # The library's text may name ids or credentials, so only the type is logged.
        logger.error("incident_folders_list_failed", error_type=type(error).__name__)
        folders = []
    if not folders:
        message = ":warning: No products could be listed. Try again; if it keeps failing, ask SRE to check the Google Drive configuration."
        client.views_update(view_id=view_id, view=_folders_modal([_text_block(message)]))
        return
    folders.sort(key=lambda x: x["name"])
    folders = folders[:LEGACY_FOLDER_DISPLAY_LIMIT]
    blocks = [item for sublist in list(map(folder_item, folders)) for item in sublist]
    client.views_update(view_id=view_id, view=_folders_modal(blocks))


def delete_folder_metadata(client: WebClient, body, ack):
    ack()
    folder_id = body["view"]["private_metadata"]
    key = body["actions"][0]["value"]
    response = incident_drive.delete_metadata(folder_id, key)
    if not response:
        logger.warning(
            "metadata_delete_failed",
            key=key,
            folder_id=folder_id,
        )
    else:
        logger.info(
            "metadata_delete_success",
            key=key,
            folder_id=folder_id,
        )
    body["actions"] = [{"value": folder_id}]
    view_folder_metadata(client, body, ack)


def save_metadata(client: WebClient, body, ack, view):
    ack()
    folder_id = view["private_metadata"]
    key = view["state"]["values"]["key"]["key"]["value"]
    value = view["state"]["values"]["value"]["value"]["value"]
    incident_drive.add_metadata(folder_id, key, value)
    body["actions"] = [{"value": folder_id}]
    del body["view"]
    view_folder_metadata(client, body, ack)


def view_folder_metadata(client, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    logger.info(
        "view_folder_metadata",
        folder_id=folder_id,
    )
    folder = incident_drive.get_metadata(folder_id, fields="id, name, appProperties")
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


def add_folder_metadata(client: WebClient, body, ack):
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
