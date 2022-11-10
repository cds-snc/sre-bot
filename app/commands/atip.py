from commands import utils
from integrations import trello

import os

from datetime import datetime

help_text = """
\n `/atip help` - show this help text | montre le dialogue d'aide
\n `/atip start` - start the ATIP process | démarre le processus AIPRP
"""

ATIP_ANNOUNCE_CHANNEL = os.environ.get("ATIP_ANNOUNCE_CHANNEL")


def atip_command(ack, command, logger, respond, client, body):
    ack()
    logger.info("Atip command received: %s", command["text"])

    if command["text"] == "":
        respond(
            "Type `/atip help` to see a list of commands. \n Tapez `/atip help` pour une liste des commandes"
        )
        return

    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            respond(help_text)
        case "start":
            request_start_modal(client, body, *args)
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/atip help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. Tapez `/atip help` pour voir une liste des commandes."
            )


def request_start_modal(client, body, ati_id=""):
    user = body["user_id"]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "atip_view",
            "title": {"type": "plain_text", "text": "Start ATIP process"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "ATIP process at CDS / Le processus ATIP à la SNC",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "Fill out the fields below and you are good to go // Remplissez les champs ici-bas et vous pourrez commencer:",
                    },
                },
                {
                    "block_id": "ati_id",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "ati_id",
                        "initial_value": ati_id,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "ATI number / Numéro ATI",
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_content",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "ati_content",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "ATI content / Contenu de l'ATI",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "block_id": "ati_search_width",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Search width / Étendue de la recherche*",
                    },
                    "accessory": {
                        "type": "checkboxes",
                        "options": [
                            {
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Slack messages / Messages Slack",
                                },
                                "value": "width_slack",
                            },
                            {
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Google drive",
                                },
                                "value": "width_drive",
                            },
                            {
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Emails / Courriels",
                                },
                                "value": "width_email",
                            },
                            {
                                "text": {"type": "mrkdwn", "text": "GitHub"},
                                "value": "width_github",
                            },
                            {
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Other SaaS / Autres outils SaaS",
                                },
                                "value": "width_other_saas",
                            },
                            {
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "All of the above / Tous",
                                },
                                "value": "width_all",
                            },
                        ],
                        "action_id": "ati_search_width",
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_due_date",
                    "element": {
                        "type": "datepicker",
                        "initial_date": datetime.today().strftime("%Y-%m-%d"),
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date / Sélectionnez une date",
                            "emoji": True,
                        },
                        "action_id": "ati_due_date",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Due date / Date d'échéance",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_request_deadline",
                    "element": {
                        "type": "datepicker",
                        "initial_date": datetime.today().strftime("%Y-%m-%d"),
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date / Sélectionnez une date",
                            "emoji": True,
                        },
                        "action_id": "ati_request_deadline",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Request deadline / Date limite de la demande",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_contact",
                    "element": {
                        "type": "users_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a contact / Sélectionnez un contact",
                        },
                        "action_id": "ati_contact",
                        "initial_user": user,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Primary contact / Contact principal",
                    },
                },
                {
                    "block_id": "ati_tbs_email",
                    "type": "input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "ati_tbs_email",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "TBS Email / Courriel TBS",
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_search_term_a",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "ati_search_term_a",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Search term A / Terme de recherche A",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_search_term_b",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "ati_search_term_b",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Search term B / Terme de recherche B",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "ati_search_term_c",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "ati_search_term_c",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Search term C / Terme de recherche C",
                        "emoji": True,
                    },
                },
            ],
        },
    )


def atip_width_action(ack):
    ack()


def atip_view_handler(ack, body, say, logger, client):
    ack()

    ati_id = body["view"]["state"]["values"]["ati_id"]["ati_id"]["value"]
    ati_content = body["view"]["state"]["values"]["ati_content"]["ati_content"]["value"]
    ati_contact = body["view"]["state"]["values"]["ati_contact"]["ati_contact"][
        "selected_user"
    ]
    ati_due_date = body["view"]["state"]["values"]["ati_due_date"]["ati_due_date"][
        "selected_date"
    ]
    ati_request_deadline = body["view"]["state"]["values"]["ati_request_deadline"][
        "ati_request_deadline"
    ]["selected_date"]
    ati_tbs_email = body["view"]["state"]["values"]["ati_tbs_email"]["ati_tbs_email"][
        "value"
    ]
    ati_search_width = body["view"]["state"]["values"]["ati_search_width"][
        "ati_search_width"
    ]["selected_options"]
    ati_search_term_a = body["view"]["state"]["values"]["ati_search_term_a"][
        "ati_search_term_a"
    ]["value"]
    ati_search_term_b = body["view"]["state"]["values"]["ati_search_term_b"][
        "ati_search_term_b"
    ]["value"]
    ati_search_term_c = body["view"]["state"]["values"]["ati_search_term_c"][
        "ati_search_term_c"
    ]["value"]

    errors = {}

    if ati_search_width == []:
        errors[
            "ati_search_width"
        ] = "Please select at least one search width / Veuillez sélectionner au moins une largeur de recherche"

    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    formatted_date = datetime.strptime(ati_due_date, "%Y-%m-%d").strftime("%d %b %Y")

    slug = f"tmp atip {ati_id}".replace(" ", "-").lower()

    # Create channel
    response = client.conversations_create(name=f"{slug}")
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")

    channel_id = response["channel"]["id"]

    # Announce atip
    user_id = body["user"]["id"]
    text = (
        f"<@{user_id}> has kicked off a new ATIP: {ati_id}"
        f" in <#{channel_id}>\n"
        f"<@{user_id}> a initié un nouvel ATIP: {ati_id}"
        f" dans <#{channel_id}>"
    )
    say(text=text, channel="C033L7RGCT0")

    # Set topic
    client.conversations_setTopic(
        channel=channel_id,
        topic=f"ATIP: {ati_id} / Due: {ati_due_date} / Contact: <@{ati_contact}>",
    )

    options_map = {
        "width_slack": "Slack messages / Messages Slack",
        "width_drive": "Google drive",
        "width_email": "Emails / Courriels",
        "width_github": "GitHub",
        "width_other_saas": "Other SaaS / Autres outils SaaS",
        "width_all": "",
    }

    options = [options_map[option["value"]] for option in ati_search_width]

    if "width_all" in [option["value"] for option in ati_search_width]:
        options = list(options_map.values())
    else:
        options = [options_map[option["value"]] for option in ati_search_width]

    en_terms = filter(
        lambda x: x is not None,
        [ati_search_term_a, ati_search_term_b, ati_search_term_c],
    )

    fr_terms = filter(
        lambda x: x is not None,
        [ati_search_term_a, ati_search_term_b, ati_search_term_c],
    )

    post_content = (
        f"""
Hello! CDS has received an Access to Information request for the following records:

{ati_content}

To fulfill this request, please search your {", ".join(options)} for the following terms:

"""
        + "\n".join([f"- {term}" for term in en_terms])
        + f"""

Please do this search by *{formatted_date}*.

If you have relevant records, please send them to the TBS email of <@{ati_contact}> at {ati_tbs_email}. A Slack channel <#{channel_id}> has been created if you have any questions. We recommend that you join that channel if you have any records. If you believe that you may have a substantial number of records (e.g. over 500 pages), please notify <@{ati_contact}> immediately.

It is important that you do not delete any records pertaining to the request for the duration of the ATI.

Thank you for your understanding! Access to information makes our democracy stronger. 💪

---

Bonjour! Le SNC a reçu une demande d’accès à l’information pour les documents suivants :

{ati_content}

Pour répondre à cette demande, veuillez rechercher les termes suivants dans votre {", ".join(options)}:

"""
        + "\n".join([f"- {term}" for term in fr_terms])
        + f"""

Veuillez effectuer cette recherche avant le *{formatted_date}*.

Si vous avez des documents pertinents, veuillez les envoyer à <@{ati_contact}> à l’adresse courriel {ati_tbs_email}. Le canal Slack <#{channel_id}>  a été créé afin que vous puissiez y poser vos questions. Nous vous recommandons de rejoindre le canal si vous avez des documents pertinents. Si vous pensez avoir un volume important de documentation (c.-à-d. plus de 500 pages), veuillez en informer <@{ati_contact}> immédiatement.

Il est important que vous ne supprimiez aucune documentation relative à la demande, et ce, pour la durée de l’accès à l’information.

Merci de votre compréhension! L’accès à l’information renforce notre démocratie. 💪
"""
    )
    say(text=post_content, channel=ATIP_ANNOUNCE_CHANNEL)
    say(text=post_content, channel=channel_id)

    # Add trello card
    trello.add_atip_card_to_trello(
        ati_id, ati_content, datetime.strptime(ati_request_deadline, "%Y-%m-%d")
    )
