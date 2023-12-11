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
VPN_PRODUCTS = os.environ.get("VPN_PRODUCTS", "").split(",")


def handle_webhook_command(args, client, body, respond):
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

def vpn_on(ack, view, body, logger, client, say):
    ack()

    errors = {}

    print(view["state"]["values"])

    product = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    reason = view["state"]["values"]["reason"]["reason"]["value"]
    if not product:
        errors["product"] = "Please select a product"
    if not reason:
        errors["reason"] = "Please enter a reason"

    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return


def vpn_on_modal(client, body):
    vpn_products = [
        {
            "text": {"type": "plain_text", "text": product["name"]},
            "value": product["id"],
        }
        for product in VPN_PRODUCTS
    ]    
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "vpn_on_view",
            "title": {"type": "plain_text", "text": "SRE - turn on AWS client VPN"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Select the product VPN that you would like to turn on",
                        "emoji": True,
                    },
                },
                {
                    "block_id": "product",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a product",
                        },
                        "options": vpn_products,
                        "action_id": "product",
                    },
                    "label": {"type": "plain_text", "text": "Product", "emoji": True},
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
                        "text": "Why is the VPN being turned on?",
                    },
                },
            ],
        },
    )
