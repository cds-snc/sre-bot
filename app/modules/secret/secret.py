"""Secret module.

This module allows users to send encrypted messages to other users.
"""

import time

import i18n  # type: ignore
import requests  # type: ignore
from core.config import settings
from core.logging import get_module_logger
from integrations.slack import users as slack_users

PREFIX = settings.PREFIX

i18n.load_path.append("./locales/")
i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")

logger = get_module_logger()


def register(bot):
    bot.command(f"/{PREFIX}secret")(secret_command)
    bot.action("secret_change_locale")(handle_change_locale_button)
    bot.view("secret_view")(secret_view_handler)


def secret_command(client, ack, command, body):
    ack()
    logger.info(
        "secret_command_received",
        command=command,
    )
    if "user" in body:
        user_id = body["user"]["id"]
    else:
        user_id = body["user_id"]
    locale = slack_users.get_user_locale(client, user_id)
    i18n.set("locale", locale)
    view = generate_secret_command_modal_view(command, user_id, locale)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def secret_view_handler(ack, client, view):
    ack()
    locale = view["blocks"][0]["elements"][0]["value"]
    i18n.set("locale", locale)
    secret = view["state"]["values"]["secret_input"]["secret_submission"]["value"]
    ttl = view["state"]["values"]["product"]["secret_ttl"]["selected_option"]["value"]

    # Encrypted message API
    endpoint = "https://encrypted-message.cdssandbox.xyz/encrypt"
    json = {"body": secret, "ttl": int(ttl) + int(time.time())}
    response = requests.post(
        endpoint, json=json, timeout=10, headers={"Content-Type": "application/json"}
    )

    try:
        id = response.json()["id"]
        url = f"https://encrypted-message.cdssandbox.xyz/{i18n.t('secret.locale_short')}/view/{id}"
        client.chat_postEphemeral(
            channel=view["private_metadata"],
            user=view["private_metadata"],
            text=f"{i18n.t('secret.link_available')} {url}",
        )
    except Exception as e:
        logger.exception(
            "secret_view_handler_error",
            exception=str(e),
            endpoint=endpoint,
        )
        client.chat_postEphemeral(
            channel=view["private_metadata"],
            user=view["private_metadata"],
            text=i18n.t("secret.error"),
        )
        return


def handle_change_locale_button(ack, client, body):
    ack()
    if "user" in body:
        user_id = body["user"]["id"]
    else:
        user_id = body["user_id"]
    locale = body["actions"][0]["value"]
    if locale == "en-US":
        locale = "fr-FR"
    else:
        locale = "en-US"
    i18n.set("locale", locale)
    command = {
        "text": body["view"]["state"]["values"]["secret_input"]["secret_submission"][
            "value"
        ]
    }
    if command["text"] is None:
        command["text"] = ""
    view = generate_secret_command_modal_view(command, user_id, locale)
    client.views_update(view_id=body["view"]["id"], view=view)


def generate_secret_command_modal_view(command, user_id, locale="en-US"):
    ttl_options = [
        {"name": "7 " + i18n.t("secret.days"), "value": "604800"},
        {"name": "3 " + i18n.t("secret.days"), "value": "259200"},
        {"name": "1 " + i18n.t("secret.day"), "value": "86400"},
        {"name": "12 " + i18n.t("secret.hours"), "value": "43200"},
        {"name": "4 " + i18n.t("secret.hours"), "value": "14400"},
        {"name": "1 " + i18n.t("secret.hour"), "value": "3600"},
        {"name": "30 " + i18n.t("secret.minutes"), "value": "1800"},
        {"name": "5 " + i18n.t("secret.minutes"), "value": "300"},
    ]

    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["value"],
        }
        for i in ttl_options
    ]
    return {
        "type": "modal",
        "private_metadata": user_id,
        "callback_id": "secret_view",
        "title": {
            "type": "plain_text",
            "text": i18n.t("secret.title"),
        },
        "submit": {
            "type": "plain_text",
            "text": i18n.t("secret.submit"),
        },
        "blocks": [
            {
                "type": "actions",
                "block_id": "locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": i18n.t("secret.locale_button"),
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "secret_change_locale",
                    }
                ],
            },
            {
                "type": "input",
                "block_id": "secret_input",
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("secret.label"),
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "secret_submission",
                    "initial_value": command["text"],
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("secret.placeholder"),
                    },
                },
            },
            {
                "block_id": "product",
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("secret.ttl"),
                    },
                    "options": options,
                    "action_id": "secret_ttl",
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("secret.ttl"),
                    "emoji": True,
                },
            },
        ],
    }
