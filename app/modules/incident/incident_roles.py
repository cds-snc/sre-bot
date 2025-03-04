import json
from slack_sdk.web import WebClient
import re
from integrations.google_workspace import google_drive


def save_incident_roles(client: WebClient, ack, view):
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
    # Get the current channel description and append the new roles
    description = client.conversations_info(channel=metadata["channel_id"])["channel"][
        "purpose"
    ]["value"]

    # Regular expression to detect any existing "IC: <@user> / OL: <@user>"
    ic_ol_pattern = r"IC: <@[\w]+> / OL: <@[\w]+>"

    # New replacement text
    new_ic_ol_text = f"\nIC: <@{selected_ic}> / OL: <@{selected_ol}>"

    if re.search(ic_ol_pattern, description):
        # If there's an existing IC/OL, replace it with the new one
        updated_description = re.sub(ic_ol_pattern, new_ic_ol_text, description)
    else:
        # Otherwise, append it to the description
        updated_description = f"{description} {new_ic_ol_text}"

    # Ensure the purpose does not exceed 250 characters
    max_length = 250
    purpose_text = updated_description[:max_length]

    # Update the Slack channel purpose
    client.conversations_setPurpose(
        channel=metadata["channel_id"], purpose=purpose_text
    )


def manage_roles(client: WebClient, body, ack, respond):
    ack()
    channel_name = body["channel_name"]
    channel_name = channel_name[
        channel_name.startswith("incident-") and len("incident-") :
    ]
    channel_name = channel_name[channel_name.startswith("dev-") and len("dev-") :]
    documents = google_drive.find_files_by_name(channel_name)

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
