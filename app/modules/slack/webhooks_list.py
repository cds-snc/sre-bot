import json
from slack_sdk.web import WebClient
from modules.slack import webhooks

from core.logging import get_module_logger

logger = get_module_logger()

MAX_BLOCK_SIZE = 16


# return the list of webhooks based on the type (active or disabled)
def get_webhooks(all_hooks, type):
    """Filter the webhooks based on the type (active or disabled) and format them for display"""
    # based on type, return the list of webhooks
    if type == "active":
        hooks = [
            webhook_list_item(hook) for hook in all_hooks if hook["active"]["BOOL"]
        ]
    elif type == "disabled":
        hooks = [
            webhook_list_item(hook) for hook in all_hooks if not hook["active"]["BOOL"]
        ]
    else:
        hooks = []
    return hooks


def webhook_list_item(hook: dict):
    hook_type: str = hook.get("hook_type", {"S": "alert"})["S"]
    hook_type = hook_type.capitalize()
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
                    "text": f"{hook['created_at']['S']} | Type: {hook_type}\n {hook['invocation_count']['N']} invocations | {hook['acknowledged_count']['N']} acknowledged",
                }
            ],
        },
        {"type": "divider"},
    ]


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
def list_all_webhooks(
    client, body, start, end, type, all_hooks, channel=None, update=False
):
    # each webhook consumes four blocks. max block size is 16. So, we need to divide the end index by 4 to get the actual number of webhooks to display
    active_hooks = get_webhooks(all_hooks, "active")
    active_hooks_list = get_webhooks_list(active_hooks)
    active_button_block = get_webhooks_button_block("active", active_hooks_list, end)

    # get the disabled webhooks and button block
    disabled_hooks = get_webhooks(all_hooks, "disabled")
    disabled_hooks_list = get_webhooks_list(disabled_hooks)
    disabled_button_block = get_webhooks_button_block(
        "disabled", disabled_hooks_list, end
    )

    if body.get("view", {"private_metadata": None}).get("private_metadata"):
        private_metadata = json.loads(body["view"]["private_metadata"])
    else:
        private_metadata = {
            "start": start,
            "end": end,
            "type": type,
            "channel": channel,
            "channel_name": body.get("channel_name", None),
        }
    header_active_hooks = f"There are currently {len(active_hooks)} enabled webhooks"
    header_disabled_hooks = (
        f"There are currently {len(disabled_hooks)} disabled webhooks"
    )
    if channel:
        suffix = f" for channel:\n{private_metadata['channel_name']}"
        header_active_hooks += suffix
        header_disabled_hooks += suffix

    # display the webhooks in the modal
    blocks = {
        "type": "modal",
        "callback_id": "webhooks_view",
        "title": {"type": "plain_text", "text": "SRE - Listing webhooks"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": json.dumps(private_metadata),
        "blocks": (
            [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_active_hooks,
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
                        "text": header_disabled_hooks,
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


def reveal_webhook(ack, body, client: WebClient):
    ack()

    username = body["user"]["username"]
    hook = webhooks.get_webhook(body["actions"][0]["value"])
    id = hook["id"]["S"]
    name = hook["name"]["S"]
    channel = hook["channel"]["S"]

    logger.info("reveal_webhook_called", user_name=username, webhook_id=id)

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
    client.views_push(
        trigger_id=body["trigger_id"],
        view=blocks,
    )


def toggle_webhook(ack, body, client):
    ack()

    username = body["user"]["username"]
    user_id = body["user"]["id"]
    hook = webhooks.get_webhook(body["actions"][0]["value"])
    id = hook["id"]["S"]
    name = hook["name"]["S"]
    channel = hook["channel"]["S"]
    private_metadata = json.loads(body["view"]["private_metadata"])

    webhooks.toggle_webhook(id)
    message = f"Webhook {name} has been {'disabled' if hook['active']['BOOL'] else 'enabled'} by <@{username}>"
    logger.info(
        "toggle_webhook_called",
        user_name=username,
        webhook_id=id,
        channel=channel,
    )
    client.chat_postMessage(
        channel=channel,
        user=user_id,
        text=message,
    )
    channel_id = private_metadata.get("channel", None)
    if channel_id:
        all_hooks = webhooks.lookup_webhooks("channel", channel_id)
    else:
        all_hooks = webhooks.list_all_webhooks()

    list_all_webhooks(
        client, body, 0, MAX_BLOCK_SIZE, "all", all_hooks, channel_id, update=True
    )


# Function to handle pagination and displaying next pages
def next_page(ack, body, client):
    ack()
    end_index, type = body["actions"][0]["value"].split(",")
    end_index = int(end_index)
    private_metadata = json.loads(body["view"]["private_metadata"])
    if private_metadata.get("channel"):
        channel = private_metadata["channel"]
        hooks = webhooks.lookup_webhooks("channel", channel)
    else:
        channel = None
        hooks = webhooks.list_all_webhooks()
    # if we go to the next page, then pudate the start and end index to be the next 4 elements. Else, display the results
    # from the beginning
    if body["actions"][0]["text"]["text"] == "Next page":
        list_all_webhooks(
            client,
            body,
            end_index,
            (end_index + MAX_BLOCK_SIZE),
            type,
            hooks,
            channel,
            update=True,
        )
    else:
        list_all_webhooks(
            client, body, 0, MAX_BLOCK_SIZE, type, hooks, channel, update=True
        )
