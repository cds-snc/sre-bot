import re
import datetime
import i18n  # type: ignore
from slack_sdk import WebClient
from slack_bolt import Ack

from integrations import opsgenie
from integrations.slack import users as slack_users
from integrations.sentinel import log_to_sentinel
from integrations.google_next.meet import GoogleMeet

from modules.incident import (
    incident_folder,
    incident_document,
    db_operations,
)
from core.logging import get_module_logger
from core.config import settings


PREFIX = settings.PREFIX
INCIDENT_CHANNEL = settings.feat_incident.INCIDENT_CHANNEL
SLACK_SECURITY_USER_GROUP_ID = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID
INCIDENT_HANDBOOK_URL = settings.feat_incident.INCIDENT_HANDBOOK_URL

logger = get_module_logger()

i18n.load_path.append("./locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")


def register(bot):
    bot.command(f"/{PREFIX}incident")(open_create_incident_modal)
    bot.view("incident_view")(submit)
    bot.action("incident_change_locale")(handle_change_locale_button)


def open_create_incident_modal(client, ack, command, body):
    ack()
    logger.info(
        "incident_command_called",
        command=command,
        body=body,
    )
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


def submit(ack: Ack, view, say, body, client: WebClient):  # noqa: C901
    # Complexity of function is too high for flake8 but currently we are ignoring this until we refactor this function.
    ack()
    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    folder = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    product = view["state"]["values"]["product"]["product"]["selected_option"]["text"][
        "text"
    ]
    security_incident = view["state"]["values"]["security_incident"][
        "security_incident"
    ]["selected_option"]["value"]

    if not re.match(r"^[\w\-\s]+$", name):
        errors["name"] = (
            "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
        )
    if len(name) > 59:
        errors["name"] = (
            "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
        )
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    logger.info(
        "incident_modal_submitted",
        name=name,
        name_length=len(name),
        folder=folder,
        product=product,
        security_incident=security_incident,
        body=body,
    )
    gmeet_scopes = ["https://www.googleapis.com/auth/meetings.space.created"]
    gmeet = GoogleMeet(scopes=gmeet_scopes)
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
    # if we are testing ie PREFIX is "dev" then create the channel with name incident-dev-{slug}. Otherwise create the channel with name incident-{slug}
    environment = "prod"
    channel_to_create = f"incident-{slug}"
    if PREFIX == "dev-":
        environment = "dev"
        channel_to_create = f"incident-dev-{slug}"
    try:
        if len(channel_to_create) > 80:
            channel_to_create = channel_to_create[:80]
        response = client.conversations_create(name=channel_to_create)
    except Exception as e:
        logger.error(
            "incident_channel_creation_failed",
            error=str(e),
            channel_name=channel_to_create,
        )
        say(
            text=":warning: Channel creation failed. Please contact the SRE team.",
            channel=body["user"]["id"],
        )
        return
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(
        "incident_channel_created",
        channel_id=channel_id,
        channel_name=channel_name,
    )

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
    meet_link = gmeet.create_space()
    client.bookmarks_add(
        channel_id=channel_id,
        title="Meet link",
        type="link",
        link=meet_link["meetingUri"],
    )

    # Create a canvas for the channel
    client.conversations_canvases_create(
        channel_id=channel_id,
        document_content={
            "type": "markdown",
            "markdown": "# Incident Canvas 📋\n\nUse this area to write/store anything you want. All you need to do is to start typing below!️",
        },
    )

    text = f"A hangout has been created at: {meet_link['meetingUri']}"
    say(text=text, channel=channel_id)

    # Create incident document
    document_id = incident_document.create_incident_document(slug, folder)
    logger.info("incident_document_created", document_id=document_id)

    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    incident_folder.add_new_incident_to_list(
        document_link, name, slug, product, channel_url
    )

    folders = incident_folder.list_incident_folders()
    team_name = "Unknown"
    for f in folders:
        if f["id"] == folder:
            team_name = f["name"]
            break

    incident_data = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "name": name,
        "user_id": user_id,
        "teams": [team_name],
        "report_url": document_link,
        "meet_url": meet_link["meetingUri"],
        "environment": environment,
    }
    incident_id = db_operations.create_incident(incident_data)
    logger.info("incident_record_created", incident_id=incident_id)

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
    if security_incident == "yes":
        # If this is a security incident, get users from the security user group
        # and add them to the list of users to invite
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

    incident_document.update_boilerplate_text(
        document_id,
        name,
        product,
        channel_url,
        ", ".join(list(map(lambda x: x["profile"]["display_name_normalized"], oncall))),
    )


def generate_incident_modal_view(command, options=[], locale="en-US"):
    handbook_string = f"For more details on what constitutes a security incident, visit our <{INCIDENT_HANDBOOK_URL}|Incident Management Handbook>"
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
            {
                "block_id": "security_incident",
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("incident.modal.security_incident_placeholder"),
                        "emoji": True,
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": i18n.t("incident.modal.security_yes"),
                                "emoji": True,
                            },
                            "value": "yes",
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": i18n.t("incident.modal.security_no"),
                                "emoji": True,
                            },
                            "value": "no",
                        },
                    ],
                    "action_id": "security_incident",
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.security_incident"),
                    "emoji": True,
                },
                "hint": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.security_incident_hint"),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": handbook_string,
                    }
                ],
            },
        ],
    }


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
