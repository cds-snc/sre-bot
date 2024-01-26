import os
import main

from unittest.mock import patch


@patch.dict(os.environ, {"PREFIX": ""})
@patch("main.SocketModeHandler")
@patch("main.App")
@patch("main.scheduled_tasks")
def test_main_invokes_socket_handler(
    mock_scheduled_tasks, mock_app, mock_socket_mode_handler
):
    main.main(mock_app)

    mock_app.command.assert_any_call("/atip")
    mock_app.command.assert_any_call("/aiprp")
    mock_app.view.assert_any_call("atip_view")
    mock_app.action.assert_any_call("ati_search_width")
    mock_app.action.assert_any_call("atip_change_locale")

    mock_app.command.assert_any_call("/aws")
    mock_app.view.assert_any_call("aws_access_view")
    mock_app.view.assert_any_call("aws_health_view")

    mock_app.command.assert_any_call("/incident")
    mock_app.view.assert_any_call("incident_view")
    mock_app.action.assert_any_call("handle_incident_action_buttons")
    mock_app.action.assert_any_call("incident_change_locale")

    mock_app.action.assert_any_call("add_folder_metadata")
    mock_app.action.assert_any_call("view_folder_metadata")
    mock_app.view.assert_any_call("view_folder_metadata_modal")
    mock_app.view.assert_any_call("add_metadata_view")
    mock_app.action.assert_any_call("delete_folder_metadata")
    mock_app.action.assert_any_call("archive_channel")
    mock_app.view.assert_any_call("view_save_incident_roles")

    mock_app.command.assert_any_call("/secret")
    mock_app.action.assert_any_call("secret_change_locale")
    mock_app.view.assert_any_call("secret_view")

    mock_app.command.assert_any_call("/sre")

    mock_app.view.assert_any_call("create_webhooks_view")
    mock_app.action.assert_any_call("toggle_webhook")
    mock_app.action.assert_any_call("reveal_webhook")

    mock_app.event.assert_any_call("reaction_added")
    mock_app.event.assert_any_call("reaction_removed")

    mock_socket_mode_handler.assert_called_once_with(
        mock_app, os.environ.get("APP_TOKEN")
    )

    mock_scheduled_tasks.init.assert_called_once_with(mock_app)
    mock_scheduled_tasks.run_continuously.assert_called_once_with()


def test_is_floppy_disk_true():
    # Test case where the reaction is 'floppy_disk'
    event = {"reaction": "floppy_disk"}
    assert (
        main.is_floppy_disk(event) is True
    ), "The function should return True for 'floppy_disk' reaction"


def test_is_floppy_disk_false():
    # Test case where the reaction is not 'floppy_disk'
    event = {"reaction": "thumbs_up"}
    assert (
        main.is_floppy_disk(event) is False
    ), "The function should return False for reactions other than 'floppy_disk'"
