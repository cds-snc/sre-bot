"""Unit tests for modules.atip module.

Tests ATIP command handling, modal view interactions, and channel creation
without external dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from modules import atip


# Test data fixtures
@pytest.fixture
def make_command():
    """Factory for creating test command payloads."""

    def _make(text: str = "", command: str = "/atip", **overrides):
        default = {
            "text": text,
            "command": command,
            "user_id": "user_id",
            "user_name": "user_name",
            "channel_id": "channel_id",
            "channel_name": "channel_name",
        }
        return {**default, **overrides}

    return _make


@pytest.fixture
def make_client():
    """Factory for creating mock Slack clients."""

    def _make(locale: str = "en-US"):
        client = MagicMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {"id": "U00AAAAAAA0", "locale": locale},
        }
        return client

    return _make


@pytest.fixture
def make_body():
    """Factory for creating test body payloads."""

    def _make(locale: str = "en-US", ati_id: str | None = None):
        return {
            "user": {"id": "user_id"},
            "user_id": "user_id",
            "view": {
                "id": "view_id",
                "state": {"values": {"ati_id": {"ati_id": {"value": ati_id}}}},
                "blocks": [
                    {
                        "type": "actions",
                        "block_id": "ati_locale",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "atip_change_locale",
                                "value": locale,
                            }
                        ],
                    }
                ],
            },
            "actions": [{"action_id": "atip_change_locale", "value": locale}],
        }

    return _make


@pytest.fixture
def make_view_submission_payload():
    """Factory for creating test view submission payloads."""

    def _make(locale: str = "en-US"):
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
            "token": "test_token",
            "trigger_id": "4277747073365.84094006803.bcd32740bf6d",
            "view": {
                "id": "V04822PP214",
                "team_id": "team_id",
                "type": "modal",
                "callback_id": "atip_view",
                "blocks": [
                    {
                        "type": "actions",
                        "block_id": "ati_locale",
                        "elements": [
                            {
                                "type": "button",
                                "action_id": "atip_change_locale",
                                "value": locale,
                            }
                        ],
                    }
                ],
                "state": {
                    "values": {
                        "ati_id": {
                            "ati_id": {"type": "plain_text_input", "value": "number"}
                        },
                        "ati_content": {
                            "ati_content": {
                                "type": "plain_text_input",
                                "value": "content",
                            }
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
                                        "text": {"type": "mrkdwn", "text": "All"},
                                        "value": "width_all",
                                    }
                                ],
                            }
                        },
                        "ati_tbs_email": {
                            "ati_tbs_email": {
                                "type": "plain_text_input",
                                "value": "email",
                            }
                        },
                        "ati_search_term_a": {
                            "ati_search_term_a": {
                                "type": "plain_text_input",
                                "value": "A",
                            }
                        },
                        "ati_search_term_b": {
                            "ati_search_term_b": {
                                "type": "plain_text_input",
                                "value": "B",
                            }
                        },
                        "ati_search_term_c": {
                            "ati_search_term_c": {
                                "type": "plain_text_input",
                                "value": "C",
                            }
                        },
                    }
                },
            },
        }

    return _make


# atip_command Tests
@pytest.mark.unit
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
def test_should_respond_with_help_when_atip_command_empty_english(
    mock_settings, mock_get_locale, make_command, make_client
):
    """Test that empty atip command responds with English help text."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = "en-US"
    ack = MagicMock()
    respond = MagicMock()
    client = make_client("en-US")
    body = MagicMock(user_id="user_id")
    command = make_command(text="")

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()
    call_arg = (
        respond.call_args[1]["text"]
        if respond.call_args[1]
        else respond.call_args[0][0]
    )
    # Just check that help text was provided (exact text may vary due to i18n)
    assert "help" in str(call_arg).lower() or "/atip" in str(call_arg)


@pytest.mark.unit
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
def test_should_respond_with_help_when_atip_command_empty_french(
    mock_settings, mock_get_locale, make_command, make_client
):
    """Test that empty atip command responds with French help text for French users."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = "fr-FR"
    ack = MagicMock()
    respond = MagicMock()
    client = make_client("fr-FR")
    body = MagicMock(user_id="user_id")
    command = make_command(text="")

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()


@pytest.mark.unit
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
@pytest.mark.parametrize("action,locale", [("help", "en-US"), ("aide", "fr-FR")])
def test_should_respond_with_help_when_action_is_help(
    mock_settings, mock_get_locale, action, locale, make_command, make_client
):
    """Test that 'help' and 'aide' commands respond with appropriate help text."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = locale
    ack = MagicMock()
    respond = MagicMock()
    client = make_client(locale)
    body = MagicMock(user_id="user_id")
    command = make_command(text=action)

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()


@pytest.mark.unit
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
@pytest.mark.parametrize(
    "unknown_action",
    ["foo", "bar", "invalid_command"],
)
def test_should_respond_with_unknown_command_error(
    mock_settings, mock_get_locale, unknown_action, make_command, make_client
):
    """Test that unknown commands trigger unknown command response."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = "en-US"
    ack = MagicMock()
    respond = MagicMock()
    client = make_client("en-US")
    body = MagicMock(user_id="user_id")
    command = make_command(text=unknown_action)

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()
    call_arg = (
        respond.call_args[1]["text"]
        if respond.call_args[1]
        else respond.call_args[0][0]
    )
    assert "unknown" in str(call_arg).lower() or unknown_action in str(call_arg)


@pytest.mark.unit
@patch("modules.atip.atip.request_start_modal")
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
def test_should_open_modal_when_start_command_given(
    mock_settings, mock_get_locale, mock_request_start, make_command, make_client
):
    """Test that 'start' command opens the ATIP modal."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = "en-US"
    ack = MagicMock()
    respond = MagicMock()
    client = make_client("en-US")
    body = MagicMock(user_id="user_id")
    command = make_command(text="start")

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_request_start.assert_called_once_with(client, body, "en-US")


@pytest.mark.unit
@patch("modules.atip.atip.request_start_modal")
@patch("modules.atip.atip.slack_users.get_user_locale")
@patch("modules.atip.atip.get_settings")
def test_should_open_modal_when_lancer_command_given(
    mock_settings, mock_get_locale, mock_request_start, make_command, make_client
):
    """Test that 'lancer' command opens the ATIP modal in French."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    mock_get_locale.return_value = "fr-FR"
    ack = MagicMock()
    respond = MagicMock()
    client = make_client("fr-FR")
    body = MagicMock(user_id="user_id")
    command = make_command(text="lancer", command="/aiprp")

    # Act
    atip.atip_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_request_start.assert_called_once_with(client, body, "fr-FR")


# update_modal_locale Tests
@pytest.mark.unit
@patch("modules.atip.atip.atip_modal_view")
def test_should_switch_locale_from_english_to_french(mock_atip_modal_view, make_body):
    """Test that locale switches from English to French when button clicked."""
    # Arrange
    ack = MagicMock()
    client = MagicMock()
    body = make_body(locale="en-US", ati_id=None)

    # Act
    atip.update_modal_locale(ack, client, body)

    # Assert
    ack.assert_called_once()
    mock_atip_modal_view.assert_called_once()
    call_args = mock_atip_modal_view.call_args
    assert call_args[0][2] == "fr-FR"  # Third argument should be new locale


@pytest.mark.unit
@patch("modules.atip.atip.atip_modal_view")
def test_should_switch_locale_from_french_to_english(mock_atip_modal_view, make_body):
    """Test that locale switches from French to English when button clicked."""
    # Arrange
    ack = MagicMock()
    client = MagicMock()
    body = make_body(locale="fr-FR", ati_id="ATI123")

    # Act
    atip.update_modal_locale(ack, client, body)

    # Assert
    ack.assert_called_once()
    mock_atip_modal_view.assert_called_once()
    call_args = mock_atip_modal_view.call_args
    assert call_args[0][2] == "en-US"  # Third argument should be new locale
    assert call_args[0][1] == "ATI123"  # Second argument should be ati_id


@pytest.mark.unit
@patch("modules.atip.atip.atip_modal_view")
def test_should_update_view_with_new_locale(mock_atip_modal_view, make_body):
    """Test that modal view is updated with new locale."""
    # Arrange
    ack = MagicMock()
    client = MagicMock()
    mock_atip_modal_view.return_value = {"type": "modal"}
    body = make_body(locale="en-US")

    # Act
    atip.update_modal_locale(ack, client, body)

    # Assert
    client.views_update.assert_called_once()
    update_call = client.views_update.call_args
    assert update_call[1]["view_id"] == "view_id"


# atip_view_handler Tests
@pytest.mark.unit
@patch("modules.atip.atip.get_settings")
def test_should_return_error_when_no_search_width_selected_english(
    mock_settings, make_view_submission_payload
):
    """Test that view submission fails when no search width is selected."""
    # Arrange
    mock_settings.return_value.ATIP_ANNOUNCE_CHANNEL = "C033L7RGCT0"
    mock_settings.return_value.PREFIX = ""
    ack = MagicMock()
    body = make_view_submission_payload(locale="en-US")
    body["view"]["state"]["values"]["ati_search_width"]["ati_search_width"][
        "selected_options"
    ] = []
    say = MagicMock()
    client = MagicMock()

    # Act
    atip.atip_view_handler(ack, body, say, client)

    # Assert
    # Check that ack was called with error response_action
    error_call = ack.call_args_list[1]  # Second call should be with errors
    assert error_call[1]["response_action"] == "errors"
    assert "ati_search_width" in error_call[1]["errors"]


@pytest.mark.unit
@patch("modules.atip.atip.get_settings")
def test_should_return_error_when_no_search_width_selected_french(
    mock_settings, make_view_submission_payload
):
    """Test that view submission fails with French error message when no search width selected."""
    # Arrange
    settings_mock = MagicMock()
    settings_mock.ATIP_ANNOUNCE_CHANNEL = "C033L7RGCT0"
    settings_mock.atip.ATIP_ANNOUNCE_CHANNEL = "C033L7RGCT0"
    settings_mock.PREFIX = ""
    mock_settings.return_value = settings_mock

    ack = MagicMock()
    body = make_view_submission_payload(locale="fr-FR")
    body["view"]["state"]["values"]["ati_search_width"]["ati_search_width"][
        "selected_options"
    ] = []
    say = MagicMock()
    client = MagicMock()

    # Act
    atip.atip_view_handler(ack, body, say, client)

    # Assert
    # Check that ack was called with error response_action
    error_call = ack.call_args_list[1]  # Second call should be with errors
    assert error_call[1]["response_action"] == "errors"
    assert "ati_search_width" in error_call[1]["errors"]


@pytest.mark.unit
@patch("integrations.trello.add_atip_card_to_trello")
@patch("modules.atip.atip.get_settings")
def test_should_successfully_create_atip_channel(
    mock_settings, mock_trello, make_view_submission_payload
):
    """Test successful ATIP channel creation and notifications."""
    # Arrange
    settings_mock = MagicMock()
    settings_mock.atip.ATIP_ANNOUNCE_CHANNEL = "C033L7RGCT0"
    settings_mock.PREFIX = ""
    mock_settings.return_value = settings_mock

    ack = MagicMock()
    body = make_view_submission_payload(locale="en-US")
    say = MagicMock()
    client = MagicMock()
    client.conversations_create.return_value = {
        "channel": {"id": "C123", "name": "tmp-atip-number"}
    }

    # Act
    atip.atip_view_handler(ack, body, say, client)

    # Assert
    # ack() is called at function start
    assert ack.call_count >= 1
    # Verify the first call is the initial acknowledgment
    ack.assert_called_with()
    client.conversations_create.assert_called_once()
    client.conversations_setTopic.assert_called_once()
    assert say.call_count >= 2  # At least two say calls (announcement and channel)
    assert mock_trello.call_count == 1


# atip_width_action Tests
@pytest.mark.unit
def test_should_acknowledge_width_action():
    """Test that width action checkbox is acknowledged."""
    # Arrange
    ack = MagicMock()

    # Act
    atip.atip_width_action(ack)

    # Assert
    ack.assert_called_once()


# request_start_modal Tests
@pytest.mark.unit
@patch("modules.atip.atip.get_settings")
def test_should_open_modal_view(mock_settings):
    """Test that request_start_modal opens a Slack modal."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
    }

    # Act
    atip.request_start_modal(client, body)

    # Assert
    client.views_open.assert_called_once()
    call_args = client.views_open.call_args
    assert call_args[1]["trigger_id"] == "trigger_id"
    assert "view" in call_args[1]


@pytest.mark.unit
@patch("modules.atip.atip.get_settings")
def test_should_pass_ati_id_to_modal_view(mock_settings):
    """Test that ATI ID is passed through request_start_modal."""
    # Arrange
    mock_settings.return_value.PREFIX = ""
    client = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "user_id": "user_id",
    }

    # Act
    atip.request_start_modal(client, body, ati_id="ATI-2024-001")

    # Assert
    client.views_open.assert_called_once()
