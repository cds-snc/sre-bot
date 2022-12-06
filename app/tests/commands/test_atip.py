from commands import atip

from unittest.mock import ANY, MagicMock, patch

help_text_fr = "\n `/atip help` - For help in English\n---\n\n `/atip aide` - montre le dialogue d'aide \n `/atip lancer` - lance le processus AIPRP"
help_text_en = "\n `/atip aide` - Pour de l'aide en français\n---\n\n `/atip help` - show this help text \n `/atip start` - start the ATIP process"


def test_atip_command_handles_empty_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    atip.atip_command(
        ack,
        {"text": "", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_en)


def test_atip_command_handles_empty_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")

    atip.atip_command(
        ack,
        {"text": "", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_fr)


def test_atip_command_handles_help_EN_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    atip.atip_command(
        ack,
        {"text": "help", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_en)


def test_atip_command_handles_help_EN_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    atip.atip_command(
        ack,
        {"text": "help", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_en)


def test_atip_command_handles_help_FR_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()

    atip.atip_command(
        ack,
        {"text": "aide", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(help_text_fr)


def test_atip_command_handles_unknown_command_EN_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    atip.atip_command(
        ack,
        {"text": "foo", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(
        "Unknown command: `foo`. Type `/atip help` to see a list of commands."
    )


def test_atip_command_handles_unknown_command_FR_client():
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale("fr")
    atip.atip_command(
        ack,
        {"text": "foo", "command": "/atip"},
        MagicMock(),
        respond,
        client,
        MagicMock(),
    )
    ack.assert_called
    respond.assert_called_with(
        "Commande inconnue: `foo`. Tapez `/atip aide` pour voir une liste des commandes."
    )


@patch("commands.atip.request_start_modal")
def test_atip_command_handles_access_EN_command(request_start_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    atip.atip_command(ack, {"text": "start"}, MagicMock(), respond, client, body)
    ack.assert_called
    request_start_modal.assert_called_with(client, body, locale="en-US")


@patch("commands.atip.request_start_modal")
def test_atip_command_handles_access_FR_command(request_start_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.users_info.return_value = helper_client_locale()
    body = MagicMock()

    atip.atip_command(ack, {"text": "lancer"}, MagicMock(), respond, client, body)
    ack.assert_called
    request_start_modal.assert_called_with(client, body, locale="fr-FR")


@patch("commands.atip.atip_modal_view")
def test_atip_action_update_locale_to_FR(atip_modal_view):
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("en-US")

    atip.update_modal_locale(ack, client, body)
    ack.assert_called
    atip_modal_view.assert_called_with("user_id", "", "fr-FR")


@patch("commands.atip.atip_modal_view")
def test_atip_action_update_locale_to_EN(atip_modal_view):
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR", "ati_id")

    atip.update_modal_locale(ack, client, body)
    ack.assert_called
    atip_modal_view.assert_called_with("user_id", "ati_id", "en-US")


def test_atip_view_handler_returns_error_if_no_search_width_is_set_EN_client():
    ack = MagicMock()
    body = helper_generate_payload("en-US")
    body["view"]["state"]["values"]["ati_search_width"]["ati_search_width"][
        "selected_options"
    ] = []

    atip.atip_view_handler(ack, body, MagicMock(), MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={"ati_search_width": "Please select at least one search width"},
    )


def test_atip_view_handler_returns_error_if_no_search_width_is_set_FR_client():
    ack = MagicMock()
    body = helper_generate_payload("fr-FR")
    body["view"]["state"]["values"]["ati_search_width"]["ati_search_width"][
        "selected_options"
    ] = []

    atip.atip_view_handler(ack, body, MagicMock(), MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={
            "ati_search_width": "Veuillez sélectionner au moins une largeur de recherche"
        },
    )


@patch("integrations.trello.add_atip_card_to_trello")
def test_atip_view_handler_success(add_atip_card_to_trello_mock):
    ack = MagicMock()
    body = helper_generate_payload("en-US")
    say = MagicMock()
    logger = MagicMock()
    client = MagicMock()

    atip.atip_view_handler(ack, body, say, logger, client)
    ack.assert_called

    client.conversations_create.assert_called_with(name="tmp-atip-number")
    client.conversations_setTopic.call_count == 1
    assert say.call_count == 3
    assert add_atip_card_to_trello_mock.call_count == 1


def test_atip_width_action_calls_ack():
    ack = MagicMock()
    atip.atip_width_action(ack)
    ack.assert_called


def test_request_start_modal():
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "view": {"state": {"values": {}}},
        "user_id": "user_id",
    }

    atip.request_start_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


def test_update_modal_locale():
    ack = MagicMock()
    client = MagicMock()
    body = helper_body_payload("fr-FR")

    atip.update_modal_locale(ack, client, body)
    ack.assert_called
    view = atip.atip_modal_view("user_id", "", "en-US")
    client.views_update.assert_called_with(view_id="view_id", view=view)

    body = helper_body_payload("en-US")

    atip.update_modal_locale(ack, client, body)
    ack.assert_called
    view = atip.atip_modal_view("user_id", "", "fr-FR")
    client.views_update.assert_called_with(view_id="view_id", view=view)


def helper_client_locale(locale=""):
    if locale == "fr":
        return {
            "ok": True,
            "user": {"id": "U00AAAAAAA0", "locale": "fr-FR"},
        }
    else:
        return {
            "ok": True,
            "user": {"id": "U00AAAAAAA0", "locale": "en-US"},
        }


def helper_body_payload(locale, ati_id=None):
    return {
        "user": {"id": "user_id"},
        "view": {
            "id": "view_id",
            "state": {"values": {"ati_id": {"ati_id": {"value": ati_id}}}},
        },
        "actions": [{"action_id": "atip_change_locale", "value": locale}],
    }


def helper_generate_payload(locale):
    return {
        "type": "view_submission",
        "team": {"id": "team_id", "domain": "slack_domain"},
        "user": {
            "id": "user_id",
            "username": "user_name",
            "name": "user",
            "team_id": "team_id",
        },
        "api_app_id": "A035GTBJ4JV",
        "token": "Qi8srvSJzorEsDuCN6W0JG2e",
        "trigger_id": "4277747073365.84094006803.bcd32740bf6d74b4df9026001587ee14",
        "view": {
            "id": "V04822PP214",
            "team_id": "team_id",
            "type": "modal",
            "private_metadata": "",
            "callback_id": "atip_view",
            "state": {
                "values": {
                    "ati_locale": {
                        "atip_change_locale": {
                            "type": "plain_text_input",
                            "value": locale,
                        }
                    },
                    "ati_id": {
                        "ati_id": {"type": "plain_text_input", "value": "number"}
                    },
                    "ati_content": {
                        "ati_content": {"type": "plain_text_input", "value": "content"}
                    },
                    "ati_due_date": {
                        "ati_due_date": {
                            "type": "datepicker",
                            "selected_date": "2022-10-26",
                        }
                    },
                    "ati_request_deadline": {
                        "ati_request_deadline": {
                            "type": "datepicker",
                            "selected_date": "2022-10-26",
                        }
                    },
                    "ati_contact": {
                        "ati_contact": {
                            "type": "users_select",
                            "selected_user": "user_id",
                        }
                    },
                    "ati_search_width": {
                        "ati_search_width": {
                            "type": "checkboxes",
                            "selected_options": [
                                {
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "All of the above / Tout ce qui précède",
                                        "verbatim": False,
                                    },
                                    "value": "width_all",
                                }
                            ],
                        }
                    },
                    "ati_tbs_email": {
                        "ati_tbs_email": {"type": "plain_text_input", "value": "email"}
                    },
                    "ati_search_term_a": {
                        "ati_search_term_a": {"type": "plain_text_input", "value": "A"}
                    },
                    "ati_search_term_b": {
                        "ati_search_term_b": {"type": "plain_text_input", "value": "B"}
                    },
                    "ati_search_term_c": {
                        "ati_search_term_c": {"type": "plain_text_input", "value": "C"}
                    },
                }
            },
            "hash": "1666814109.Xy8x4mLq",
            "title": {
                "type": "plain_text",
                "text": "Start ATIP process",
                "emoji": True,
            },
            "clear_on_close": False,
            "notify_on_close": False,
            "close": None,
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "previous_view_id": None,
            "root_view_id": "V04822PP214",
            "app_id": "A035GTBJ4JV",
            "external_id": "",
            "app_installed_team_id": "team_id",
            "bot_id": "B034XMCNG0N",
        },
        "response_urls": [],
        "is_enterprise_install": False,
        "enterprise": None,
    }
