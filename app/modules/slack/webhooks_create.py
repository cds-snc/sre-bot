import os
import re
from modules.slack import webhooks

PREFIX = os.environ.get("PREFIX", "")


def handle_create_webhook_action(ack, view, body, logger, client, say):
    ack()

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    channel = view["state"]["values"]["channel"]["channel"]["selected_channel"]
    hook_type = view["state"]["values"]["hook_type"]["hook_type"]["selected_option"][
        "value"
    ]
    hook_type = hook_type if hook_type else "alert"
    hook_type = hook_type.lower()
    user = body["user"]["id"]

    if not re.match(r"^[\w\-\s]+$", name):
        errors["name"] = "Description must only contain number and letters"
    if len(name) > 80:
        errors["name"] = "Description must be less than 80 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    id = webhooks.create_webhook(channel, user, name, hook_type)
    client.conversations_join(channel=channel)
    if id:
        message = f"Webhook created with url: https://sre-bot.cdssandbox.xyz/hook/{id}"
        logger.info(message)
        say(channel=channel, text=f"<@{user}> created a new SRE-Bot webhook: {name}")
    else:
        message = "Something went wrong creating the webhook"
        logger.error(f"Error creating webhook: {channel}, {user}, {name}")

    client.chat_postEphemeral(
        channel=channel,
        user=user,
        text=message,
    )


def create_webhook_modal(client, body):
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "create_webhooks_view",
            "title": {"type": "plain_text", "text": "SRE - Create a webhook"},
            "submit": {"type": "plain_text", "text": "Create"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Create a new webhook by filling out the fields below:",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "name",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "name",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Short description (ex: notify prod alerts)",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Select a channel for the webhook",
                        "emoji": True,
                    },
                },
                {
                    "type": "actions",
                    "block_id": "channel",
                    "elements": [
                        {
                            "type": "channels_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select a channel for the webhook",
                                "emoji": True,
                            },
                            "initial_channel": body["channel_id"],
                            "action_id": "channel",
                        }
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Select a type of webhook (defaults to alert)",
                        "emoji": True,
                    },
                },
                {
                    "type": "actions",
                    "block_id": "hook_type",
                    "elements": [
                        {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select a type",
                                "emoji": True,
                            },
                            "options": [
                                {
                                    "text": {"type": "plain_text", "text": "Alert"},
                                    "value": "alert",
                                },
                                {
                                    "text": {"type": "plain_text", "text": "Info"},
                                    "value": "info",
                                },
                            ],
                            "initial_option": {
                                "text": {"type": "plain_text", "text": "Alert"},
                                "value": "alert",
                            },
                            "action_id": "hook_type",
                        }
                    ],
                },
            ],
        },
    )
