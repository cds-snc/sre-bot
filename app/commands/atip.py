from commands import utils
from integrations import trello

import os
import i18n

from datetime import datetime

i18n.load_path.append("./commands/locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")


def atip_command(ack, command, logger, respond, client, body):
    ack()
    user_id = body["user_id"]
    i18n.set("locale", utils.get_user_locale(user_id, client))
    logger.info("Atip command received: %s", command["text"])
    if command["text"] == "":
        respond(i18n.t("atip.help_text", command=command["command"]))
        return
    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            i18n.set("locale", "en-US")
            respond(i18n.t("atip.help_text", command=command["command"]))
        case "aide":
            i18n.set("locale", "fr-FR")
            respond(i18n.t("atip.help_text", command=command["command"]))
        case "start":
            i18n.set("locale", "en-US")
            request_start_modal(client, body, locale="en-US", *args)
        case "lancer":
            i18n.set("locale", "fr-FR")
            request_start_modal(client, body, locale="fr-FR", *args)
        case _:
            respond(
                i18n.t(
                    "atip.unknown_command", action=action, command=command["command"]
                )
            )


def atip_modal_view(user, ati_id, locale):
    view = {
        "type": "modal",
        "callback_id": "atip_view",
        "title": {"type": "plain_text", "text": i18n.t("atip.modal.title")},
        "submit": {"type": "plain_text", "text": i18n.t("atip.modal.submit")},
        "blocks": [
            {
                "type": "actions",
                "block_id": "ati_locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": i18n.t("atip.locale_button"),
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "atip_change_locale",
                    },
                ],
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.process_header"),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.process_instructions"),
                },
            },
            {
                "block_id": "ati_id",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "ati_id",
                    "initial_value": ati_id,
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.ati_number"),
                },
            },
            {
                "type": "input",
                "block_id": "ati_content",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "ati_content",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.ati_content"),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "block_id": "ati_search_width",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{i18n.t('atip.modal.ati_search_width')}*",
                },
                "accessory": {
                    "type": "checkboxes",
                    "options": [
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.slack"),
                            },
                            "value": "width_slack",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.google_drive"),
                            },
                            "value": "width_drive",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.emails"),
                            },
                            "value": "width_email",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.github"),
                            },
                            "value": "width_github",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.saas"),
                            },
                            "value": "width_other_saas",
                        },
                        {
                            "text": {
                                "type": "mrkdwn",
                                "text": i18n.t("atip.modal.all"),
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
                        "text": i18n.t("atip.modal.select_date_placeholder"),
                        "emoji": True,
                    },
                    "action_id": "ati_due_date",
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.ati_due_date"),
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
                        "text": i18n.t("atip.modal.select_date_placeholder"),
                        "emoji": True,
                    },
                    "action_id": "ati_request_deadline",
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.ati_request_deadline"),
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
                        "text": i18n.t("atip.modal.select_contact"),
                    },
                    "action_id": "ati_contact",
                    "initial_user": user,
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.primary_contact"),
                },
            },
            {
                "block_id": "ati_tbs_email",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "ati_tbs_email",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.tbs_email"),
                },
            },
            {
                "type": "input",
                "block_id": "ati_search_term_a",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "ati_search_term_a",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.search_term_a"),
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.search_term_b"),
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
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("atip.modal.placeholder_write_something"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("atip.modal.search_term_c"),
                    "emoji": True,
                },
            },
        ],
    }
    return view


def request_start_modal(client, body, locale="", ati_id=""):
    user = body["user_id"]
    if locale == "":
        locale = "en-US"
    i18n.set("locale", locale)
    view = atip_modal_view(user, ati_id, locale)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def update_modal_locale(ack, client, body):
    ack()
    user = body["user"]["id"]
    ati_id = body["view"]["state"]["values"]["ati_id"]["ati_id"]["value"]
    if ati_id is None:
        ati_id = ""
    locale = next(
        (
            action
            for action in body["actions"]
            if action["action_id"] == "atip_change_locale"
        ),
        None,
    )["value"]
    if locale == "en-US":
        locale = "fr-FR"
    else:
        locale = "en-US"
    i18n.set("locale", locale)
    view_id = body["view"]["id"]
    view = atip_modal_view(user, ati_id, locale)
    client.views_update(view_id=view_id, view=view)


def atip_width_action(ack):
    ack()


def atip_view_handler(ack, body, say, logger, client):
    ack()

    ati_locale = body["view"]["state"]["values"]["ati_locale"]["atip_change_locale"][
        "value"
    ]
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

    i18n.set("locale", ati_locale)
    if ati_search_width == []:
        errors["ati_search_width"] = i18n.t("atip.modal.search_width_error")

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
    say(text=post_content, channel=os.environ.get("ATIP_ANNOUNCE_CHANNEL"))
    say(text=post_content, channel=channel_id)

    # Add trello card
    trello.add_atip_card_to_trello(
        ati_id, ati_content, datetime.strptime(ati_request_deadline, "%Y-%m-%d")
    )
