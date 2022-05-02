from commands import utils

from integrations import aws_sso
from commands.utils import log_ops_message

help_text = """
\n `/aws help` - show this help text
\n `/aws access` - starts the process to access and AWS account"""


def aws_command(ack, command, logger, respond, client, body):
    ack()
    logger.info("AWS command received: %s", command["text"])

    if command["text"] == "":
        respond("Type `/aws help` to see a list of commands.")
        return

    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            respond(help_text)
        case "access":
            request_modal(client, body)
        case _:
            respond(
                f"Unknown command: {action}. Type `/aws help` to see a list of commands."
            )


def access_view_handler(ack, body, logger, respond, client):
    ack()
    user = body["user"]["name"]
    user_id = body["user"]["id"]
    account = body["view"]["state"]["values"]["account"]["account"]["selected_option"][
        "value"
    ]
    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]
    access_type = body["view"]["state"]["values"]["access_type"]["access_type"][
        "selected_option"
    ]["value"]
    rationale = body["view"]["state"]["values"]["rationale"]["rationale"]["value"]
    msg = f"<@{user_id}> ({user}) requested access to {account_name} ({account}) with {access_type} priviliges.\n\nRationale: {rationale}"
    logger.info(msg)
    # log_ops_message(client, msg)
    # aws_sso.request_access(account, access_type, rationale)
    # respond("Access request sent.")


def request_modal(client, body):
    accounts = aws_sso.get_accounts()
    options = [
        {
            "text": {"type": "plain_text", "text": value},
            "value": key,
        }
        for key, value in accounts.items()
    ]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "aws_access_view",
            "title": {"type": "plain_text", "text": "AWS - Account access"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "block_id": "account",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select an account you want access to",
                        },
                        "options": options,
                        "action_id": "account",
                    },
                    "label": {"type": "plain_text", "text": "Account", "emoji": True},
                },
                {
                    "block_id": "access_type",
                    "type": "input",
                    "label": {
                        "type": "plain_text",
                        "text": "What type of access do you want? :this-is-fine-fire:",
                        "emoji": True,
                    },
                    "element": {
                        "type": "radio_buttons",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Read access - just need to check something",
                                    "emoji": True,
                                },
                                "value": "read",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Write access - need to modify something",
                                    "emoji": True,
                                },
                                "value": "write",
                            },
                        ],
                        "action_id": "access_type",
                    },
                },
                {
                    "type": "input",
                    "block_id": "rationale",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "rationale",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "What do you plan on doing?",
                        "emoji": True,
                    },
                },
            ],
        },
    )
