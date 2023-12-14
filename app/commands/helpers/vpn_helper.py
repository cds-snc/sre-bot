import os


help_text = """
\n `/sre vpn on`
\n      - turn on the VPN 
\n      - activer le RVP
\n `/sre vpn off`
\n      - turn off the VPN
\n      - désactiver le RPV
\n `/sre vpn status`
\n      - get the VPN's status
\n      - obtenir le statut du RPV
"""

# Comma separated list of products that have an AWS client VPN installed
VPN_DURATIONS = os.environ.get("VPN_DURATIONS", "1,4,8").split(",")
VPN_PRODUCTS = os.environ.get("VPN_PRODUCTS", "").split(",")


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
                        "text": "Select the VPN you would like to turn on",
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
                        "options": get_select_options(VPN_PRODUCTS),
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
                        "options": get_select_options(VPN_DURATIONS, transform=lambda time: f"{time} hour{'' if time == '1' else 's'}"),
                        "action_id": "duration",
                    },
                    "label": {"type": "plain_text", "text": "How long should it stay on?", "emoji": True},
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

    errors = {}

    user = body["user"]["id"]
    vpn = view["state"]["values"]["vpn"]["vpn"]["selected_option"]["value"]
    duration = view["state"]["values"]["duration"]["duration"]["selected_option"]["value"]
    reason = view["state"]["values"]["reason"]["reason"]["value"]

    if not vpn:
        errors["vpn"] = "Please select a VPN to turn on"
    if not reason:
        errors["reason"] = "Please enter a reason"
    if duration not in VPN_DURATIONS:
        errors["duration"] = "Please select a valid duration"

    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return
    
    result = f":large_green_circle: `{vpn}` VPN turning on for `{duration} hour{'' if duration == '1' else 's'}`.  This can take a few minutes and you can check with `/sre vpn status`.\n\nThe VPN is being turned on for the following reason:\n```{reason}```"
    logger.info("VPN On: vpn: %s, duration: %s, reason: %s, slack user: %s, ", vpn, duration, reason, body["user"])
    client.chat_postMessage(channel=user, text=result)


def get_select_options(options_list, transform=lambda x: x):
    "Helper function to generate a list of select options"
    return [
        {
            "text": {"type": "plain_text", "text": f"{transform(option)}", "emoji": True},
            "value": option,
        }
        for option in options_list
    ]