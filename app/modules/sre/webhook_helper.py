"""Webhook helper functions for the SRE Bot."""

from modules.slack import webhooks_create, webhooks_list, webhooks

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
    bot.view("create_webhooks_view")(webhooks_create.handle_create_webhook_action)
    bot.action("toggle_webhook")(webhooks_list.toggle_webhook)
    bot.action("reveal_webhook")(webhooks_list.reveal_webhook)
    bot.action("next_page")(webhooks_list.next_page)
    bot.action("channel")(ack_action)
    bot.action("hook_type")(ack_action)


def ack_action(ack):
    ack()


def handle_webhook_command(args, client, body, respond):
    if len(args) == 0:
        hooks = webhooks.lookup_webhooks("channel", body["channel_id"])
        if hooks:
            webhooks_list.list_all_webhooks(
                client,
                body,
                0,
                MAX_BLOCK_SIZE,
                "all",
                hooks,
                channel=body["channel_id"],
            )
        else:
            respond(
                "No webhooks found for this channel. Type `/sre webhooks help` to see a list of commands."
            )
        return

    action, *args = args
    match action:
        case "create":
            webhooks_create.create_webhook_modal(client, body)
        case "help":
            respond(help_text)
        case "list":
            hooks = webhooks.list_all_webhooks()
            if hooks:
                webhooks_list.list_all_webhooks(
                    client, body, 0, MAX_BLOCK_SIZE, "all", hooks
                )
            else:
                respond("No webhooks found.")
        case _:
            respond(
                f"Unknown command: `{action}`. "
                "Type `/sre webhooks help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. "
                "Tapez `/sre webhooks help` pour voir une liste de commandes."
            )
