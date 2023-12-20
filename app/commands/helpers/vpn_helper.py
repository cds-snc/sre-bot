import os
import datetime

from integrations.aws_client_vpn import AWSClientVPN


help_text = """
\n `/sre vpn on`
\n      - turn on the VPN
\n      - activer le RVP
\n `/sre vpn status`
\n      - get the VPN's status
\n      - obtenir le statut du RPV
"""

VPN_DURATION_HOURS = os.environ.get("VPN_DURATION_HOURS", "1,4,8").split(",")
VPN_PRODUCTS = {
    "Notify": {
        "channel_id": os.environ.get("VPN_NOTIFY_CHANNEL_ID"),
        "vpn_id": os.environ.get("VPN_NOTIFY_ID"),
        "role_arn": os.environ.get("VPN_NOTIFY_ROLE_ARN"),
    }
}


def handle_vpn_command(args, client, body, respond):
    "Top level routing of the VPN subcommands"
    if len(args) == 0:
        respond(help_text)
        return

    action, *args = args
    match action:
        case "help":
            respond(help_text)
        case "on":
            vpn_on_modal(client, body)
        case "status":
            vpn_status_modal(client, body)
        case _:
            respond(
                f"Unknown command: `{action}`. "
                "Type `/sre vpn help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. "
                "Tapez `/sre vpn help` pour voir une liste de commandes."
            )


def vpn_on_modal(client, body):
    "Open the VPN on modal"
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "vpn_on",
            "title": {"type": "plain_text", "text": "SRE - VPN On"},
            "submit": {"type": "plain_text", "text": "Turn on"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Select the VPN to turn on",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "vpn",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a VPN",
                        },
                        "options": get_select_options(VPN_PRODUCTS.keys()),
                        "action_id": "vpn",
                    },
                    "label": {"type": "plain_text", "text": "VPN", "emoji": True},
                },
                {
                    "block_id": "duration",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a duration",
                        },
                        "options": get_select_options(
                            VPN_DURATION_HOURS,
                            transform=lambda time: f"{time} hour{'' if time == '1' else 's'}",
                        ),
                        "action_id": "duration",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "How long should it stay on?",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "reason",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Why is it being turned on?",
                    },
                },
            ],
        },
    )


def vpn_on(ack, view, client, body, logger):
    "VPN on modal submission handler"
    ack()

    # Get inputs and validate
    errors = {}
    user = body["user"]["id"]
    vpn = view["state"]["values"]["vpn"]["vpn"]["selected_option"]["value"]
    duration = view["state"]["values"]["duration"]["duration"]["selected_option"][
        "value"
    ]
    reason = view["state"]["values"]["reason"]["reason"]["value"]
    if vpn not in VPN_PRODUCTS.keys():
        errors["vpn"] = "Please select a VPN from the dropdown"
    if not reason:
        errors["reason"] = "Please enter a reason"
    if duration not in VPN_DURATION_HOURS:
        errors["duration"] = "Please select a valid duration"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    # Get the VPN status and respond to the user
    client_vpn = AWSClientVPN(
        name=vpn,
        reason=reason,
        duration=duration,
        vpn_id=VPN_PRODUCTS[vpn]["vpn_id"],
        assume_role_arn=VPN_PRODUCTS[vpn]["role_arn"],
    )
    status = client_vpn.turn_on()
    if status in [AWSClientVPN.STATUS_ON, AWSClientVPN.STATUS_TURNING_ON]:
        result = (
            f"{get_status_icon(status)} The `{vpn}` VPN is `{status}` for {pluralize(int(duration), 'hour')}:\n"
            f"```Reason: {reason}```\n\n"
            f"This can take up to 5 minutes.  Use the following to check the status.\n"
            f"```/sre vpn status```"
        )
    else:
        result = f"{get_status_icon(status)} There was an error turning on the `{vpn}` VPN.  Please contact SRE for help."
    logger.info(
        "VPN On: vpn: %s, duration: %s, reason: %s, slack user: %s, ",
        vpn,
        duration,
        reason,
        body["user"],
    )
    client.chat_postEphemeral(
        channel=VPN_PRODUCTS[vpn]["channel_id"], text=result, user=user
    )


def vpn_status_modal(client, body):
    "Open the VPN status modal"
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "vpn_status",
            "title": {"type": "plain_text", "text": "SRE - VPN Status"},
            "submit": {"type": "plain_text", "text": "Get status"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Select the VPN",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "vpn",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a VPN",
                        },
                        "options": get_select_options(VPN_PRODUCTS.keys()),
                        "action_id": "vpn",
                    },
                    "label": {"type": "plain_text", "text": "VPN", "emoji": True},
                },
            ],
        },
    )


def vpn_status(ack, view, client, body, logger):
    "VPN status modal submission handler"
    ack()

    # Get inputs and validate
    errors = {}
    user = body["user"]["id"]
    vpn = view["state"]["values"]["vpn"]["vpn"]["selected_option"]["value"]
    if vpn not in VPN_PRODUCTS.keys():
        errors["vpn"] = "Please select a VPN from the dropdown"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    # Get the VPN status and respond to the user
    client_vpn = AWSClientVPN(
        name=vpn,
        vpn_id=VPN_PRODUCTS[vpn]["vpn_id"],
        assume_role_arn=VPN_PRODUCTS[vpn]["role_arn"],
    )
    status = client_vpn.get_status()
    status_code = status.get("status")
    session = status.get("session")
    result = f"{get_status_icon(status_code)} The `{vpn}` VPN is `{status_code}`"

    # If the VPN is on, add the remaining time and reason
    if session and status_code in [
        AWSClientVPN.STATUS_ON,
        AWSClientVPN.STATUS_TURNING_ON,
    ]:
        if status_code == AWSClientVPN.STATUS_ON:
            remaining_seconds = (
                float(session["expires_at"]["N"]) - datetime.datetime.now().timestamp()
            )
            if (
                remaining_seconds > 0
            ):  # Checking for the edge case where the VPN will turn off momentarily
                remaining_hours = int(remaining_seconds / 3600)
                remaining_minutes = int(remaining_seconds % 3600 / 60)
                result += f" for{' ' + pluralize(remaining_hours, 'hour') if remaining_hours > 0 else ''}{' ' + pluralize(remaining_minutes, 'minute') if remaining_minutes > 0 else ''}:\n"
        else:
            result += f" for {pluralize(int(session['duration']['N']), 'hour')}:\n"
        result += f"```Reason: {session['reason']['S']}```"

    logger.info(
        "VPN status: vpn: %s, status: %s, slack user: %s, ",
        vpn,
        status,
        body["user"],
    )
    client.chat_postEphemeral(
        channel=VPN_PRODUCTS[vpn]["channel_id"], text=result, user=user
    )


def get_select_options(options_list, transform=lambda x: x):
    "Helper function to generate a list of select options"
    return [
        {
            "text": {
                "type": "plain_text",
                "text": f"{transform(option)}",
                "emoji": True,
            },
            "value": option,
        }
        for option in options_list
    ]


def get_status_icon(status):
    "Helper function to get the icon for the status"
    if status == AWSClientVPN.STATUS_ON:
        return ":green:"
    elif status == AWSClientVPN.STATUS_TURNING_ON:
        return ":beach-ball:"
    else:
        return ":red:"


def pluralize(number, string):
    "Helper function to pluralize a string"
    return f"{number} {string}{'s' if number != 1 else ''}"
