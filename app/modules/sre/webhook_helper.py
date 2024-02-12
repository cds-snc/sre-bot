"""Webhook helper functions for the SRE Bot."""

import re

from models import webhooks

help_text = """
\n `/sre webhooks create`
\n      - create a new webhook
\n      - créer un nouveau webhook
\n `/sre webhooks help`
\n      - show this help text
\n      - montrer ce texte d'aide
\n `/sre webhooks list`
\n      - lists webhooks
\n      - lister les webhooks
"""

# see 4 webhooks at a time. This is done to avoid hitting the 100 block size limit and for the view to be more managable to see.
# has to be divisible by 4 since each webhook is 4 blocks
MAX_BLOCK_SIZE = 16


def register(bot):
    bot.view("create_webhooks_view")(create_webhook)
    bot.action("toggle_webhook")(toggle_webhook)
    bot.action("reveal_webhook")(reveal_webhook)
    bot.action("next_page")(next_page)


def handle_webhook_command(args, client, body, respond):
    if len(args) == 0:
        respond(help_text)
        return

    action, *args = args
    match action:
        case "create":
            create_webhook_modal(client, body)
        case "help":
            respond(help_text)
        case "list":
            list_all_webhooks(client, body, 0, MAX_BLOCK_SIZE, "all")
        case _:
            respond(
                f"Unknown command: `{action}`. "
                "Type `/sre webhooks help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. "
                "Tapez `/sre webhooks help` pour voir une liste de commandes."
            )


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


# return the list of webhooks based on the type (active or disabled)
def get_webhooks(type):
    all_hooks = webhooks.list_all_webhooks()
    # based on type, return the list of webhooks
    if type == "active":
        hooks = list(
            map(
                lambda hook: webhook_list_item(hook),
                filter(lambda hook: hook["active"]["BOOL"], all_hooks),
            )
        )
    elif type == "disabled":
        hooks = list(
            map(
                lambda hook: webhook_list_item(hook),
                filter(lambda hook: not hook["active"]["BOOL"], all_hooks),
            )
        )
    else:
        # unrecongized type, return empty list
        hooks = []
    return hooks


# function to flatten the webhooks and return them in a flattened list
def get_webhooks_list(hooks):
    return [item for sublist in hooks for item in sublist]


# generate the button for the webhook. If there are more than 4 webhooks (MAX_BLOCK_SIZE/the number of elements in a block list),
# show the next page button. Otherwise, show nothing
def get_webhooks_button_block(type, hooks_list, end):
    if len(hooks_list) > (MAX_BLOCK_SIZE / 4):
        button_block = [
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": (
                                "Next page" if end < len(hooks_list) else "First page"
                            ),
                            "emoji": True,
                        },
                        "value": f"{end},{type}",
                        "action_id": "next_page",
                    }
                ],
            }
        ]
    else:
        button_block = []
    return button_block


# Get and return all webhooks. Start is the index of the first webhook to show, end is the index of the last webhook to show.
# Type is the type of webhooks to show (active, disabled, or all)
def list_all_webhooks(client, body, start, end, type, update=False):
    # get the active webhooks and button block
    active_hooks = get_webhooks("active")
    active_hooks_list = get_webhooks_list(active_hooks)
    active_button_block = get_webhooks_button_block("active", active_hooks_list, end)

    # get the disabled webhooks and button block
    disabled_hooks = get_webhooks("disabled")
    disabled_hooks_list = get_webhooks_list(disabled_hooks)
    disabled_button_block = get_webhooks_button_block(
        "disabled", disabled_hooks_list, end
    )

    # display the webhooks in the modal
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
            # this is used to traverse the list of webhooks for the pagination. Show the webhooks slice of array based on
            # start and end index
            + (
                active_hooks_list[start:end]
                if type == "active" or type == "all"
                else active_hooks_list[0:MAX_BLOCK_SIZE]
            )
            # display the button block
            + active_button_block
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
            + (
                disabled_hooks_list[start:end]
                if type == "disabled" or type == "all"
                else disabled_hooks_list[0:MAX_BLOCK_SIZE]
            )
            + disabled_button_block
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
    list_all_webhooks(client, body, 0, MAX_BLOCK_SIZE, "all", update=True)


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
                "text": "<#{}>".format(hook["channel"]["S"]),
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
                    "text": f"{hook['created_at']['S']} \n {hook['invocation_count']['N']} invocations | {hook['acknowledged_count']['N']} acknowledged",
                }
            ],
        },
        {"type": "divider"},
    ]


# Function to handle pagination and displaying next pages
def next_page(ack, body, client):
    ack()
    end_index, type = body["actions"][0]["value"].split(",")
    end_index = int(end_index)

    # if we go to the next page, then pudate the start and end index to be the next 4 elements. Else, display the results
    # from the beginning
    if body["actions"][0]["text"]["text"] == "Next page":
        list_all_webhooks(
            client, body, end_index, (end_index + MAX_BLOCK_SIZE), type, update=True
        )
    else:
        list_all_webhooks(client, body, 0, MAX_BLOCK_SIZE, type, update=True)
