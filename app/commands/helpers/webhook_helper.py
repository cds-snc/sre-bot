import re

from models import webhooks

help_text = """
\n `/sre webhooks create` - create a new webhook
\n `/sre webhooks help` - show this help text
\n `/sre webhooks list` - lists webhooks
"""


def handle_webhook_command(args, client, body):
    if len(args) == 0:
        return help_text

    action, *args = args
    match action:
        case "create":
            create_webhook_modal(client, body)
        case "help":
            return help_text
        case "list":
            list_all_webhooks(client, body)
        case _:
            return f"Unknown command: {action}. Type `/sre webhook help` to see a list of commands."


def create_webhook(ack, view, body, logger, client, say):
    ack()

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    channel = view["state"]["values"]["channel"]["channel"]["selected_channel"]
    user = body["user"]["id"]

    if not re.match(r"^[\w\-\s]+$", name):
        errors["name"] = "Description must only contain number and letters"
    if len(name) > 80:
        errors["name"] = "Description must be less than 80 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    id = webhooks.create_webhook(channel, user, name)
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
            ],
        },
    )


def list_all_webhooks(client, body, update=False):

    hooks = webhooks.list_all_webhooks()
    active_hooks = list(
        map(
            lambda hook: webhook_list_item(hook),
            filter(lambda hook: hook["active"]["BOOL"], hooks),
        )
    )
    disabled_hooks = list(
        map(
            lambda hook: webhook_list_item(hook),
            filter(lambda hook: not hook["active"]["BOOL"], hooks),
        )
    )

    blocks = {
        "type": "modal",
        "callback_id": "webhooks_view",
        "title": {"type": "plain_text", "text": "SRE - Listing webhooks"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": (
            [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"There are currently {len(active_hooks)} enabled webhooks",
                    },
                },
                {"type": "divider"},
            ]
            + [item for sublist in active_hooks for item in sublist]
            + [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"There are currently {len(disabled_hooks)} disabled webhooks",
                    },
                },
                {"type": "divider"},
            ]
            + [item for sublist in disabled_hooks for item in sublist]
        ),
    }
    if update:
        client.views_update(
            view_id=body["view"]["id"],
            view=blocks,
        )
    else:
        client.views_open(trigger_id=body["trigger_id"], view=blocks)


def reveal_webhook(ack, body, logger, client):
    ack()

    username = body["user"]["username"]
    hook = webhooks.get_webhook(body["actions"][0]["value"])
    id = hook["id"]["S"]
    name = hook["name"]["S"]
    channel = hook["channel"]["S"]

    message = f"{username} has requested to see the webhook with ID: {id}"
    logger.info(message)

    blocks = {
        "type": "modal",
        "callback_id": "webhooks_view",
        "title": {"type": "plain_text", "text": "SRE - Reveal webhook"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Revealing webhook {name} for channel: <#{channel}>",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"https://sre-bot.cdssandbox.xyz/hook/{id}",
                },
            },
        ],
    }

    client.views_update(
        view_id=body["view"]["id"],
        view=blocks,
    )


def toggle_webhook(ack, body, logger, client):
    ack()

    username = body["user"]["username"]
    user_id = body["user"]["id"]
    hook = webhooks.get_webhook(body["actions"][0]["value"])
    id = hook["id"]["S"]
    name = hook["name"]["S"]
    channel = hook["channel"]["S"]

    webhooks.toggle_webhook(id)
    message = f"Webhook {name} has been {'enabled' if hook['active']['BOOL'] else 'disabled'} by <@{username}>"
    logger.info(message)
    client.chat_postMessage(
        channel=channel,
        user=user_id,
        text=message,
    )
    list_all_webhooks(client, body, update=True)


def webhook_list_item(hook):
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": hook["name"]["S"]},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reveal", "emoji": True},
                "style": "primary",
                "value": hook["id"]["S"],
                "action_id": "reveal_webhook",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": " in  <#{}>".format(hook["channel"]["S"]),
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ("Disable" if hook["active"]["BOOL"] else "Enable"),
                    "emoji": True,
                },
                "style": "danger",
                "value": hook["id"]["S"],
                "action_id": "toggle_webhook",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "emoji": True,
                    "text": f"on {hook['created_at']['S']}",
                }
            ],
        },
        {"type": "divider"},
    ]
