from commands import utils

from integrations import aws_sso
from commands.utils import log_ops_message
from models import aws_access_requests

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


def access_view_handler(ack, body, logger, client):
    ack()

    errors = {}

    rationale = body["view"]["state"]["values"]["rationale"]["rationale"]["value"]

    if len(rationale) > 2000:
        errors["rationale"] = "Please use less than 2000 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    user_id = body["user"]["id"]

    user = client.users_info(user=user_id)["user"]
    email = user["profile"]["email"]

    account = body["view"]["state"]["values"]["account"]["account"]["selected_option"][
        "value"
    ]

    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]

    access_type = body["view"]["state"]["values"]["access_type"]["access_type"][
        "selected_option"
    ]["value"]

    msg = f"<@{user_id}> ({email}) requested access to {account_name} ({account}) with {access_type} priviliges.\n\nRationale: {rationale}"

    logger.info(msg)
    log_ops_message(client, msg)
    aws_user_id = aws_sso.get_user_id(email)

    if aws_user_id is None:
        msg = f"<@{user_id}> ({email}) is not registered with AWS SSO. Please contact your administrator."
    elif expires := aws_access_requests.already_has_access(
        account, user_id, access_type
    ):
        msg = f"You already have access to {account_name} ({account}) with access type {access_type}. Your access will expire in {expires} minutes."
    elif aws_access_requests.create_aws_access_request(
        account, account_name, user_id, email, access_type, rationale
    ) and aws_sso.add_permissions_for_user(aws_user_id, account, access_type):
        msg = f"Provisioning {access_type} access request for {account_name} ({account}). This can take a minute or two. Visit <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> to gain access."
    else:
        msg = f"Failed to provision {access_type} access request for {account_name} ({account}). Please drop a note in the <#sre-and-tech-ops> channel."

    client.chat_postEphemeral(
        channel=user_id,
        user=user_id,
        text=msg,
    )


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
