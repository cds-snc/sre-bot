import re
import i18n  # type: ignore
from slack_sdk import WebClient
from slack_bolt import Ack, App

from integrations.slack import users as slack_users
from integrations.sentinel import log_to_sentinel
from models.incidents import IncidentPayload

from modules.incident import (
    incident_conversation,
    incident_folder,
    core,
)
from core.logging import get_module_logger
from core.config import settings


PREFIX = settings.PREFIX
INCIDENT_CHANNEL = settings.feat_incident.INCIDENT_CHANNEL
SLACK_SECURITY_USER_GROUP_ID = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID
INCIDENT_HANDBOOK_ID = settings.google_resources.incident_handbook_id

logger = get_module_logger()

i18n.load_path.append("./locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")


def register(bot: App):
    bot.command(f"/{PREFIX}incident")(open_create_incident_modal)
    bot.view("incident_view")(submit)
    bot.action("incident_change_locale")(handle_change_locale_button)


def open_create_incident_modal(client: WebClient, ack, command, body):
    ack()
    # private_metadata = json.dumps(
    #     {
    #         "channel_id": body["channel"]["id"],
    #         "message_ts": body["message_ts"],
    #     }
    # )
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
    loaded_view = generate_incident_modal_view(command, options, None, locale)
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
    view = generate_incident_modal_view(command, options, None, locale)
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

    channel_id = None
    channel_name = None
    slug = None
    user_id = body["user"]["id"]

    # private_metadata = json.loads(body["view"].get("private_metadata"))
    # source_channel_id = private_metadata.get("channel_id")
    # source_message_ts = private_metadata.get("message_ts")
    try:
        channel_created = incident_conversation.create_incident_conversation(
            client, name
        )
        channel_id = channel_created["channel_id"]
        channel_name = channel_created["channel_name"]
        slug = channel_created["slug"]

    except Exception as e:
        logger.error(
            "incident_channel_creation_failed",
            error=str(e),
            incident_name=name,
        )
        say(
            text=":warning: Channel creation failed. Please contact the SRE team.",
            channel=body["user"]["id"],
        )
        return

    # if private_metadata:
    #     # private_metadata = json.loads(private_metadata)
    #     logger.info("private_metadata_found", private_metadata=private_metadata)
    #     incident_alert.update_alert_with_channel_link(
    #         client,
    #         source_channel_id,
    #         source_message_ts,
    #         incident_details={"channel_id": channel_id, "channel_name": channel_name},
    #     )

    logger.info(
        "incident_channel_created",
        channel_id=channel_id,
        channel_name=channel_name,
        slug=slug,
    )

    view = generate_success_modal(body, channel_id, channel_name)
    client.views_open(trigger_id=body["trigger_id"], view=view)

    logger.info(
        "incident_modal_submitted",
        name=name,
        name_length=len(name),
        folder=folder,
        product=product,
        security_incident=security_incident,
        body=body,
    )
    log_to_sentinel("incident_called", body)

    incident_payload = IncidentPayload(
        name=name,
        folder=folder,
        product=product,
        security_incident=security_incident,
        user_id=user_id,
        channel_id=channel_id,
        channel_name=channel_name,
        slug=slug,
    )
    try:
        core.initiate_resources_creation(
            client=client,
            incident_payload=incident_payload,
        )
    except Exception as e:
        logger.error(
            "incident_resources_creation_failed",
            error=str(e),
            incident_name=name,
            channel_id=channel_id,
        )
        say(
            text=":warning: There was an error initiating the incident resources. Please contact the SRE team.",
            channel=channel_id,
        )
        return


def generate_incident_modal_view(
    command, options=None, private_metadata=None, locale="en-US"
):
    """Generate the incident creation modal view."""
    if options is None:
        options = []
    if not private_metadata:
        private_metadata = ""
    handbook_string = f"For more details on what constitutes a security incident, visit our <https://docs.google.com/document/d/{INCIDENT_HANDBOOK_ID}|Incident Management Handbook>"
    return {
        "type": "modal",
        "callback_id": "incident_view",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "submit": {"type": "plain_text", "text": i18n.t("incident.submit")},
        "private_metadata": private_metadata,
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
