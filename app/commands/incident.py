import os
import re
import datetime

from integrations import google_drive, opsgenie
from models import webhooks

from dotenv import load_dotenv

load_dotenv()

INCIDENT_CHANNEL = os.environ.get("INCIDENT_CHANNEL")


def handle_incident_action_buttons(client, ack, body):
    name = body["actions"][0]["name"]
    value = body["actions"][0]["value"]
    user = body["user"]["id"]
    if name == "call-incident":
        open_modal(client, ack, {"text": value}, body)
    elif name == "ignore-incident":
        ack()
        webhooks.increment_acknowledged_count(value)
        attachments = body["original_message"]["attachments"]
        msg = f"🙈  <@{user}> has acknowledged and ignored the incident."
        attachments[-1] = {
            "color": "3AA3E3",
            "fallback": f"{msg}",
            "text": f"{msg}",
        }
        body["original_message"]["attachments"] = attachments
        body["original_message"]["channel"] = body["channel"]["id"]
        client.api_call("chat.update", json=body["original_message"])


def open_modal(client, ack, command, body):
    ack()
    folders = google_drive.list_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]

    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "incident_view",
            "title": {"type": "plain_text", "text": "SRE - Start an incident"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Congratulations!",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Something has gone wrong. You've got this!",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "This app is going to help you get set up. It will create the following: \n \n • a channel \n • an incident report \n • a Google Meet",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Fill out the two fields below and you are good to go:",
                    },
                },
                {
                    "block_id": "name",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "name",
                        "initial_value": command["text"],
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Short description (ex: too many 500 errors)",
                    },
                },
                {
                    "block_id": "product",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a product",
                        },
                        "options": options,
                        "action_id": "product",
                    },
                    "label": {"type": "plain_text", "text": "Product", "emoji": True},
                },
            ],
        },
    )


def submit(ack, view, say, body, client, logger):

    ack()

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    folder = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    product = view["state"]["values"]["product"]["product"]["selected_option"]["text"][
        "text"
    ]

    if not re.match(r"^[\w\-\s]+$", name):
        errors["name"] = "Description must only contain number and letters"
    if len(name) > 80:
        errors["name"] = "Description must be less than 80 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    # Get folder metadata
    folder_metadata = google_drive.list_metadata(folder).get("appProperties", {})
    oncall = []

    # Get OpsGenie data
    if "genie_schedule" in folder_metadata:
        for email in opsgenie.get_on_call_users(folder_metadata["genie_schedule"]):
            r = client.users_lookupByEmail(email=email)
            if r.get("ok"):
                oncall.append(r["user"])

    date = datetime.datetime.now().strftime("%Y-%m-%d")
    slug = f"{date} {name}".replace(" ", "-").lower()

    # Create channel
    response = client.conversations_create(name=f"incident-{slug}")
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")

    channel_id = response["channel"]["id"]
    channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"

    # Set topic
    client.conversations_setTopic(
        channel=channel_id, topic=f"Incident: {name} / {product}"
    )

    # Announce incident
    user_id = body["user"]["id"]
    text = f"<@{user_id}> has kicked off a new incident: {name} for {product} in <#{channel_id}>"
    say(text=text, channel=INCIDENT_CHANNEL)

    # Add meeting link
    meet_link = f"https://g.co/meet/incident-{slug}"
    client.bookmarks_add(
        channel_id=channel_id, title="Meet link", type="link", link=meet_link
    )

    text = f"A hangout has been created at: {meet_link}"
    say(text=text, channel=channel_id)

    # Create incident document
    document_id = google_drive.create_new_incident(slug, folder)
    logger.info(f"Created document: {slug} in folder: {folder} / {document_id}")

    # Merge data
    google_drive.merge_data(
        document_id,
        name,
        product,
        channel_url,
        ", ".join(list(map(lambda x: x["profile"]["display_name_normalized"], oncall))),
    )
    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    google_drive.update_incident_list(document_link, name, slug, product, channel_url)

    # Bookmark incident document
    client.bookmarks_add(
        channel_id=channel_id,
        title="Incident report",
        type="link",
        link=document_link,
    )

    text = f":lapage: An incident report has been created at: {document_link}"
    say(text=text, channel=channel_id)

    # Invite oncall to channel
    for user in oncall:
        client.conversations_invite(channel=channel_id, users=user["id"])

    text = "Run `/sre incident roles` to assign roles to the incident"
    say(text=text, channel=channel_id)
