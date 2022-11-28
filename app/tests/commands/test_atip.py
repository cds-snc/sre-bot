from commands import atip
import i18n

from unittest.mock import ANY, MagicMock, patch


def test_atip_command_handles_empty_command():
    ack = MagicMock()
    respond = MagicMock()

    atip.atip_command(ack, {"text": ""}, MagicMock(), respond, MagicMock(), MagicMock())
    ack.assert_called
    assert respond.called


def test_atip_command_handles_help_command():
    ack = MagicMock()
    respond = MagicMock()

    atip.atip_command(
        ack, {"text": "help"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    assert respond.called_with(i18n.t("atip.help_text"))


def test_atip_command_handles_unknown_command():
    ack = MagicMock()
    respond = MagicMock()

    atip.atip_command(
        ack, {"text": "foo"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    assert respond.called_with(i18n.t("atip.help_text"))


@patch("commands.atip.request_start_modal")
def test_atip_command_handles_access_command(request_start_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()

    atip.atip_command(ack, {"text": "start"}, MagicMock(), respond, client, body)
    ack.assert_called
    assert request_start_modal.called_with(client, body)


def test_atip_view_handler_returns_error_if_no_search_width_is_set():
    ack = MagicMock()
    body = helper_generate_payload()
    body["view"]["state"]["values"]["ati_search_width"]["ati_search_width"][
        "selected_options"
    ] = []

    atip.atip_view_handler(ack, body, MagicMock(), MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={
            "ati_search_width": i18n.t("atip.modal.search_width_error")
        },
    )


@patch("integrations.trello.add_atip_card_to_trello")
def test_atip_view_handler_success(add_atip_card_to_trello_mock):
    ack = MagicMock()
    body = helper_generate_payload()
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


def helper_generate_payload():
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
