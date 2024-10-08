import os
import re
import datetime
import i18n  # type: ignore
from dotenv import load_dotenv
from slack_sdk import WebClient

from integrations import opsgenie
from integrations.slack import users as slack_users
from integrations.sentinel import log_to_sentinel

from modules.incident import (
    incident_alert,
    incident_conversation,
    incident_folder,
    incident_document,
)

load_dotenv()

i18n.load_path.append("./locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")

INCIDENT_CHANNEL = os.environ.get("INCIDENT_CHANNEL")
SLACK_SECURITY_USER_GROUP_ID = os.environ.get("SLACK_SECURITY_USER_GROUP_ID")
PREFIX = os.environ.get("PREFIX", "")


def register(bot):
    bot.command(f"/{PREFIX}incident")(open_modal)
    bot.view("incident_view")(submit)
    bot.action("handle_incident_action_buttons")(
        incident_alert.handle_incident_action_buttons
    )
    bot.action("incident_change_locale")(handle_change_locale_button)
    bot.event("reaction_added", matchers=[is_floppy_disk])(
        incident_conversation.handle_reaction_added
    )
    bot.event("reaction_removed", matchers=[is_floppy_disk])(
        incident_conversation.handle_reaction_removed
    )
    bot.event("reaction_added")(just_ack_the_rest_of_reaction_events)
    bot.event("reaction_removed")(just_ack_the_rest_of_reaction_events)


# Make sure that we are listening only on floppy disk reaction
def is_floppy_disk(event: dict) -> bool:
    return event["reaction"] == "floppy_disk"


# We need to ack all other reactions so that they don't get processed
def just_ack_the_rest_of_reaction_events():
    pass


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
                        "action_id": "incident_change_locale",
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
    if "user" in body:
        user_id = body["user"]["id"]
    else:
        user_id = body["user_id"]
    locale = slack_users.get_user_locale(client, user_id)
    i18n.set("locale", locale)
    loading_view = {
        "type": "modal",
        "callback_id": "incident_view",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "submit": {"type": "plain_text", "text": i18n.t("incident.submit")},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":beach-ball: {i18n.t('incident.modal.launching')}",
                },
            },
        ],
    }
    view = client.views_open(trigger_id=body["trigger_id"], view=loading_view)["view"]
    folders = incident_folder.list_incident_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]
    loaded_view = generate_incident_modal_view(command, options, locale)
    client.views_update(view_id=view["id"], view=loaded_view)


def handle_change_locale_button(ack, client, body):
    ack()
    folders = incident_folder.list_incident_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]
    locale = body["actions"][0]["value"]
    if locale == "en-US":
        locale = "fr-FR"
    else:
        locale = "en-US"
    i18n.set("locale", locale)
    command = {"text": body["view"]["state"]["values"]["name"]["name"]["value"]}
    if command["text"] is None:
        command["text"] = ""
    view = generate_incident_modal_view(command, options, locale)
    client.views_update(view_id=body["view"]["id"], view=view)


def submit(ack, view, say, body, client: WebClient, logger):
    ack()

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    folder = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    product = view["state"]["values"]["product"]["product"]["selected_option"]["text"][
        "text"
    ]

    if not re.match(r"^[\w\-\s]+$", name):
        errors["name"] = (
            "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
        )
    if len(name) > 60:
        errors["name"] = (
            "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
        )
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    log_to_sentinel("incident_called", body)

    # Get folder metadata
    folder_metadata = incident_folder.get_folder_metadata(folder).get(
        "appProperties", {}
    )
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
    # if we are testing ie PREFIX is "dev" then create the channel with name incident-dev-{slug}. Otherwisse create the channel with name incident-{slug}
    if PREFIX == "dev-":
        response = client.conversations_create(name=f"incident-dev-{slug}")
    else:
        response = client.conversations_create(name=f"incident-{slug}")
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")

    view = generate_success_modal(body, channel_id, channel_name)
    client.views_open(trigger_id=body["trigger_id"], view=view)

    channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"

    # Set topic
    client.conversations_setTopic(
        channel=channel_id, topic=f"Incident: {name} / {product}"
    )

    # Set the description
    client.conversations_setPurpose(channel=channel_id, purpose=f"{name}")

    # Announce incident
    user_id = body["user"]["id"]
    text = (
        f"<@{user_id}> has kicked off a new incident: {name} for {product}"
        f" in <#{channel_id}>\n"
        f"<@{user_id}> a initié un nouvel incident: {name} pour {product}"
        f" dans <#{channel_id}>"
    )
    say(text=text, channel=INCIDENT_CHANNEL)

    # Add incident creator to channel
    client.conversations_invite(channel=channel_id, users=user_id)

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
    document_id = incident_document.create_incident_document(slug, folder)
    logger.info(f"Created document: {slug} in folder: {folder} / {document_id}")

    incident_document.update_boilerplate_text(
        document_id,
        name,
        product,
        channel_url,
        ", ".join(list(map(lambda x: x["profile"]["display_name_normalized"], oncall))),
    )
    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    incident_folder.add_new_incident_to_list(
        document_link, name, slug, product, channel_url
    )
    # Bookmark incident document
    client.bookmarks_add(
        channel_id=channel_id,
        title="Incident report",
        type="link",
        link=document_link,
    )

    text = f":lapage: An incident report has been created at: {document_link}"
    say(text=text, channel=channel_id)

    # Gather all user IDs in a list to ensure uniqueness
    users_to_invite = []

    # Add oncall users, excluding the user_id
    for user in oncall:
        if user["id"] != user_id:
            users_to_invite.append(user["id"])

    # Get users from the @security group
    response = client.usergroups_users_list(usergroup=SLACK_SECURITY_USER_GROUP_ID)

    # if we are testing, ie PREFIX is "dev" then don't add the security group users since we don't want to spam them
    if response.get("ok") and PREFIX == "":
        for security_user in response["users"]:
            if security_user != user_id:
                users_to_invite.append(security_user)

    # Invite all collected users to the channel in a single API call
    if users_to_invite:
        client.conversations_invite(channel=channel_id, users=users_to_invite)

    text = "Run `/sre incident roles` to assign roles to the incident"
    say(text=text, channel=channel_id)

    text = "Run `/sre incident close` to update the status of the incident document and incident spreadsheet to closed and to archive the channel"
    say(text=text, channel=channel_id)

    text = "Run `/sre incident schedule` to let the SRE bot schedule a Retro Google calendar meeting for all participants."
    say(text=text, channel=channel_id)


def generate_success_modal(body, channel_id, channel_name):
    locale = body["view"]["blocks"][0]["elements"][0]["value"]
    if locale != "fr-FR":
        locale = "en-US"
    i18n.set("locale", locale)
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "close": {"type": "plain_text", "text": "OK"},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.success"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{i18n.t('incident.modal.user_added')} <#{channel_id}|{channel_name}>",
                },
            },
            {
                "type": "divider",
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.next_steps"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.next_steps_instructions"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.brief_up"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.planned_testing"),
                },
            },
        ],
    }
