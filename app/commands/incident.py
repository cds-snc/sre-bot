import os
import re
import datetime

from integrations import google_drive

from dotenv import load_dotenv

load_dotenv()

INCIDENT_CHANNEL = os.environ.get("INCIDENT_CHANNEL")


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

    date = datetime.datetime.now().strftime("%Y-%m-%d")
    slug = f"{date} {name}".replace(" ", "-").lower()

    response = client.conversations_create(name=f"incident-{slug}")
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")

    channel_id = response["channel"]["id"]
    channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"

    client.conversations_setTopic(
        channel=channel_id, topic=f"Incident: {name} / {product}"
    )

    user_id = body["user"]["id"]
    text = f"<@{user_id}> has kicked off a new incident: {name} for {product} in <#{channel_id}>"
    say(text=text, channel=INCIDENT_CHANNEL)

    meet_link = f"https://g.co/meet/incident-{slug}"
    client.bookmarks_add(
        channel_id=channel_id, title="Meet link", type="link", link=meet_link
    )

    text = f"A hangout has been created at: {meet_link}"
    say(text=text, channel=channel_id)

    document_id = google_drive.create_new_incident(slug, folder)
    logger.info(f"Created document: {slug} in folder: {folder} / {document_id}")
    google_drive.merge_data(document_id, name, product, channel_url)
    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    google_drive.update_incident_list(document_link, name, slug, product, channel_url)

    client.bookmarks_add(
        channel_id=channel_id,
        title="Incident report",
        type="link",
        link=document_link,
    )

    text = f":lapage: An incident report has been created at: {document_link}"
    say(text=text, channel=channel_id)
