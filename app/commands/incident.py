import os
import re
import datetime
import i18n

from integrations import google_drive, opsgenie
from models import webhooks
from commands.utils import log_to_sentinel, get_user_locale

from dotenv import load_dotenv

load_dotenv()

i18n.load_path.append("./commands/locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")

INCIDENT_CHANNEL = os.environ.get("INCIDENT_CHANNEL")


def handle_incident_action_buttons(client, ack, body, logger):
    delete_block = False
    name = body["actions"][0]["name"]
    value = body["actions"][0]["value"]
    user = body["user"]["id"]
    if name == "call-incident":
        open_modal(client, ack, {"text": value}, body)
        log_to_sentinel("call_incident_button_pressed", body)
    elif name == "ignore-incident":
        ack()
        webhooks.increment_acknowledged_count(value)
        attachments = body["original_message"]["attachments"]
        msg = (
            f"🙈  <@{user}> has acknowledged and ignored the incident.\n"
            f"<@{user}> a pris connaissance et ignoré l'incident."
        )
        attachments[-1] = {
            "color": "3AA3E3",
            "fallback": f"{msg}",
            "text": f"{msg}",
        }
        body["original_message"]["attachments"] = attachments
        body["original_message"]["channel"] = body["channel"]["id"]

        # rich_text blocks are only available for 1st party Slack clients (meaning Desktop, iOS, Android Slack apps)
        # https://github.com/slackapi/bolt-js/issues/1324
        if "blocks" in body["original_message"]:
            for block in body["original_message"]["blocks"]:
                if "type" in block and block["type"] == "rich_text":
                    delete_block = True

        if delete_block:
            body["original_message"]["blocks"] = []

        logger.info(f"Updating chat: {body['original_message']}")
        client.api_call("chat.update", json=body["original_message"])
        log_to_sentinel("ignore_incident_button_pressed", body)


def generate_incident_modal_view(command, options=[], locale="en-US"):
    return {
        "type": "modal",
        "callback_id": "incident_view",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "submit": {"type": "plain_text", "text": i18n.t("incident.submit")},
        "blocks": [
            {
                "type": "actions",
                "block_id": "locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": i18n.t("incident.locale_button"),
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "change_locale",
                    }
                ],
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.congratulations"),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.something_wrong"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.app_help"),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.fill_the_fields"),
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
                    "text": i18n.t("incident.modal.description"),
                },
            },
            {
                "block_id": "product",
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("incident.modal.product"),
                    },
                    "options": options,
                    "action_id": "product",
                },
                "label": {"type": "plain_text", "text": "Product", "emoji": True},
            },
        ],
    }


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
    user_id = body["user_id"]
    locale = get_user_locale(user_id, client)
    i18n.set("locale", locale)
    view = generate_incident_modal_view(command, options, locale)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def handle_change_locale_button(ack, client, command, body, view):
    ack()
    folders = google_drive.list_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]
    user_id = body["user_id"]
    locale = get_user_locale(user_id, client)
    view = generate_incident_modal_view(command, options, locale)


def submit(ack, view, say, body, client, logger):

    ack()

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    folder = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    product = view["state"]["values"]["product"]["product"]["selected_option"]["text"][
        "text"
    ]

    if not re.match(r"^[\w\-\s]+$", name):
        errors[
            "name"
        ] = "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
    if len(name) > 80:
        errors[
            "name"
        ] = "Description must be less than 80 characters // La description doit contenir moins de 80 caractères"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    log_to_sentinel("incident_called", body)

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
    text = (
        f"<@{user_id}> has kicked off a new incident: {name} for {product}"
        f" in <#{channel_id}>\n"
        f"<@{user_id}> a initié un nouvel incident: {name} pour {product}"
        f" dans <#{channel_id}>"
    )
    say(text=text, channel=INCIDENT_CHANNEL)

    # Add meeting link
    meet_link = f"https://g.co/meet/incident-{slug}"
    # Max character length for Google Meet nickname is 60, 78 with constant URI
    if len(meet_link) > 78:
        meet_link = meet_link[:78]
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

    # Reminder to brief up
    text = ":rotating_light: If this is a cybersecurity incident, please initiate the briefing process for CCCS and TBS OCIO Cyber"
    say(text=text, channel=channel_id)

    # Invite oncall to channel
    for user in oncall:
        client.conversations_invite(channel=channel_id, users=user["id"])

    text = "Run `/sre incident roles` to assign roles to the incident"
    say(text=text, channel=channel_id)
