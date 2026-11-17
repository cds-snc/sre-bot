import uuid
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from modules import incident_helper

# Legacy command tests to be removed once transition period is over


@patch("modules.incident.incident_helper.incident_drive.create_folder")
def test_legacy_handle_incident_command_with_create_command(mock_create_folder):
    mock_create_folder.return_value = {"id": "test_id", "name": "foo bar"}
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack)
    mock_create_folder.assert_called_once_with("foo bar", ANY)

    respond.assert_has_calls(
        [
            call(
                "The `/sre incident create-folder` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident create folder <folder_name>` instead."
            ),
            call("Product `foo bar` created."),
        ]
    )


@patch("modules.incident.incident_helper.incident_drive.create_folder")
def test_legacy_handle_incident_command_with_create_command_error(mock_create_folder):
    mock_create_folder.return_value = None
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond, ack)
    respond.assert_has_calls(
        [
            call(
                "The `/sre incident create-folder` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident create folder <folder_name>` instead."
            ),
            call("Failed to create product `foo bar`."),
        ]
    )


@patch("modules.incident.incident_helper.incident_folder.list_folders_view")
def test_legacy_handle_incident_command_with_list_folders(mock_list_folders):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["list-folders"], client, body, respond, ack)
    mock_list_folders.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.stale_incidents")
def test_legacy_handle_incident_stale_command(mock_stale_incidents):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["stale"], client, body, respond, ack)
    mock_stale_incidents.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.handle_legacy_stale")
def test_legacy_handle_incident_stale_command_calls_new_handler(
    mock_handle_legacy_stale,
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["stale"], client, body, respond, ack)
    mock_handle_legacy_stale.assert_called_once_with(client, body, respond, ack, [], {})


# New command tests


def test_handle_incident_command_with_empty_args():
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    body = MagicMock()
    incident_helper.handle_incident_command([], client, body, respond, ack)
    respond.assert_called_once_with("Please provide a valid command. Type `/sre incident help` to see a list of commands.")


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command(["foo"], MagicMock(), MagicMock(), respond, ack)
    respond.assert_called_once_with("Unknown command: foo. Type `/sre incident help` to see a list of commands.")


@pytest.mark.parametrize("command", ["summary", "add_summary"])
def test_handle_incident_command_treats_removed_summary_commands_as_unknown(command):
    """summary and add_summary are no longer handled: the only reply is the unknown-command text.

    The client is a mock so any modal or channel post would be recorded; none happens.
    """
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_incident_command([command], client, {"channel_id": "channel_id"}, respond, ack)
    respond.assert_called_once_with(f"Unknown command: {command}. Type `/sre incident help` to see a list of commands.")
    client.views_open.assert_not_called()
    client.chat_postMessage.assert_not_called()


def test_handle_incident_command_dispatches_to_correct_handler():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    handler_map = {}
    handler_map.update(incident_helper.get_resource_handlers())
    handler_map.update(incident_helper.get_incident_actions())

    for first_arg, handler in handler_map.items():
        handler_name = handler.__name__
        with patch(f"modules.incident.incident_helper.{handler_name}") as handler_mock:
            args = [first_arg, "dummy_action"]
            incident_helper.handle_incident_command(args, client, body, respond, ack)
            assert handler_mock.called, f"{handler_name} should be called for first_arg '{first_arg}'"


# Incident level actions


def test_handle_help():
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["help"], MagicMock(), MagicMock(), respond, ack)
    respond.assert_called_once_with(incident_helper.help_text)


def test_handle_help_with_french():
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()

    incident_helper.handle_help(client, body, respond, ack, ["fr"], {})
    respond.assert_called_once_with(incident_helper.help_text_fr)


@patch("modules.incident.incident_helper.information_display.open_incident_info_view")
def test_handle_show(mock_open_incident_info_view):
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()

    incident_helper.handle_show(client, body, respond, ack, [], {})
    mock_open_incident_info_view.assert_called_once_with(client, body, respond)


def test_handle_list_without_resource():
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()
    list_help_text = """`/sre incident list [options]`

*Options:*
• `active` — lists all active incidents (default; not stale or archived)
• `stale` — lists all incidents older than 14 days with no activity

Use `/sre incident help` to see a list of commands."""

    incident_helper.handle_list(client, body, respond, ack, [], {})
    respond.assert_called_once_with(list_help_text)


def test_handle_list_with_active():
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()

    incident_helper.handle_list(client, body, respond, ack, ["active"], {})
    respond.assert_called_once_with("Upcoming feature: list all active incidents.")


@patch("modules.incident.incident_helper.stale_incidents")
def test_handle_list_with_stale(mock_stale_incidents):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_list(client, body, respond, ack, ["stale"], {})
    mock_stale_incidents.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.schedule_retro")
def test_handle_schedule_with_no_option(mock_schedule_retro):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_schedule(client, body, respond, ack, [], {})
    mock_schedule_retro.open_incident_retro_modal.assert_called_once_with(client, body, ack)


def test_handle_schedule_with_invalid_option():
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()
    schedule_help_text = """`/sre incident schedule [options]`

*Options:*
• `retro` — schedule a retrospective for the incident

Use `/sre incident help` to see a list of commands."""
    incident_helper.handle_schedule(client, body, respond, ack, ["asdf"], {})
    respond.assert_called_once_with(schedule_help_text)


@patch("modules.incident.incident_helper.schedule_retro")
def test_handle_schedule_with_retro(mock_schedule_retro):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_schedule(client, body, respond, ack, ["retro"], {})
    mock_schedule_retro.open_incident_retro_modal.assert_called_once_with(client, body, ack)


@patch("modules.incident.incident_helper.schedule_retro")
def test_handle_incident_command_with_schedule(mock_schedule_retro):
    client = MagicMock()
    body = {
        "channel_id": "channel_id",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "user_id",
    }
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_incident_command(["schedule", "retro"], client, body, respond, ack)
    mock_schedule_retro.open_incident_retro_modal.assert_called_once_with(client, body, ack)


# resource level actions


def test_handle_channels_with_no_action():
    respond = MagicMock()
    ack = MagicMock()
    client = MagicMock()
    body = MagicMock()
    channels_help_text = """`/sre incident channels <action> [options] [arguments]`

*Actions:*
• `<Upcoming feature>` — manage incident channels"""
    incident_helper.handle_channels(client, body, respond, ack, None, [], {})
    respond.assert_called_once_with(channels_help_text)


def test_handle_products_with_no_action():
    respond = MagicMock()
    ack = MagicMock()
    product_help_text = """`/sre incident products <action> [options] [arguments]`

*Actions:*
• `create <product_name>` — create a new product name to be referenced in the incident resources
  _Tip: Use quotes for multi-word product names: `create "product name"`_
• `list` — list all products currently available in the incident resources

Use `/sre incident help` to see a list of commands."""
    incident_helper.handle_products(MagicMock(), MagicMock(), respond, ack, None, [], {})
    respond.assert_called_once_with(product_help_text)


@patch("modules.incident.incident_helper.incident_drive.create_folder")
def test_handle_products_with_create(mock_create_folder):
    mock_create_folder.return_value = {"id": "test_id", "name": "foo bar"}
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_products(MagicMock(), MagicMock(), respond, ack, "create", ["foo", "bar"], {})
    mock_create_folder.assert_called_once_with("foo bar", ANY)

    respond.assert_called_once_with("Product `foo bar` created.")


@patch("modules.incident.incident_helper.incident_drive.create_folder")
def test_handle_products_create_without_name(mock_create_folder):
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_products(MagicMock(), MagicMock(), respond, ack, "create", [], {})

    respond.assert_called_once_with("Please provide a product name using `create <product_name>`")


@patch("modules.incident.incident_helper.incident_drive.create_folder")
def test_handle_products_with_create_error(mock_create_folder):
    mock_create_folder.return_value = None
    respond = MagicMock()
    ack = MagicMock()

    incident_helper.handle_products(MagicMock(), MagicMock(), respond, ack, "create", ["foo", "bar"], {})
    mock_create_folder.assert_called_once_with("foo bar", ANY)

    respond.assert_called_once_with("Failed to create product `foo bar`.")


@pytest.mark.parametrize("action", ["add", "show", "help", "bogus"])
def test_handle_updates_answers_every_action_with_the_status_update_pointer(action):
    """Every updates action replies once with the EN/FR pointer to /sre incident status-update.

    The client is a mock so any modal or channel post would be recorded; none happens.
    """
    client = MagicMock()
    respond = MagicMock()
    ack = MagicMock()
    incident_helper.handle_updates(client, {"channel_id": "channel_id"}, respond, ack, action, [], {})
    respond.assert_called_once_with(
        "`/sre incident updates` has been retired. "
        "Use `/sre incident status-update` to draft, review and approve a public status update."
        "\n\n"
        "`/sre incident updates` a été retirée. "
        "Utilisez `/sre incident status-update` pour rédiger, réviser et approuver une mise à jour publique."
    )
    client.views_open.assert_not_called()
    client.chat_postMessage.assert_not_called()


@patch("modules.incident.incident_helper.slack_channels.get_stale_channels")
def test_stale_incidents(get_stale_channels_mock):
    client = MagicMock()
    body = {"trigger_id": "foo"}
    ack = MagicMock()
    get_stale_channels_mock.return_value = [{"id": "id", "topic": {"value": "topic_value"}}]
    client.views_open.return_value = {"view": {"id": "view_id"}}
    incident_helper.stale_incidents(client, body, ack)
    ack.assert_called_once()
    client.views_open.assert_called_once_with(trigger_id="foo", view=ANY)
    client.views_update.assert_called_once_with(view_id="view_id", view=ANY)


def test_channel_item():
    assert incident_helper.channel_item({"id": "id", "topic": {"value": "topic_value"}}) == [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "<#id>",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "topic_value",
                }
            ],
        },
        {"type": "divider"},
    ]


def test_parse_incident_datetime_string():
    assert incident_helper.parse_incident_datetime_string("2025-01-23 17:02:16.915368") == "2025-01-23 17:02"
    assert incident_helper.parse_incident_datetime_string("2025-01-23 17:02") == "Unknown"
    assert incident_helper.parse_incident_datetime_string("") == "Unknown"
    assert incident_helper.parse_incident_datetime_string("asdf") == "Unknown"
    with pytest.raises(TypeError):
        incident_helper.parse_incident_datetime_string(None)


def test_convert_timestamp():
    assert incident_helper.convert_timestamp("1234567890") == "2009-02-13 23:31:30"
    assert incident_helper.convert_timestamp("1234567890.123456") == "2009-02-13 23:31:30"

    assert incident_helper.convert_timestamp("asdf") == "Unknown"


def generate_incident_data(
    created_at="1234567890",
    incident_commander=None,
    operations_lead=None,
    severity=None,
    start_impact_time=None,
    end_impact_time=None,
    detection_time=None,
    retrospective_url=None,
    environment="prod",
):
    id = str(uuid.uuid4())
    incident_data = {
        "id": id,
        "created_at": created_at,
        "channel_id": "channel_id",
        "channel_name": "channel_name",
        "name": "name",
        "status": "status",
        "user_id": "user_id",
        "teams": ["team1", "team2"],
        "report_url": "report_url",
        "meet_url": "meet_url",
        "environment": environment,
        "incident_commander": "incident_commander",
    }

    for key, value in [
        ("incident_commander", incident_commander),
        ("operations_lead", operations_lead),
        ("severity", severity),
        ("start_impact_time", start_impact_time),
        ("end_impact_time", end_impact_time),
        ("detection_time", detection_time),
        ("retrospective_url", retrospective_url),
    ]:
        if value:
            incident_data[key] = value

    return incident_data


# -- store-unavailable tests --
