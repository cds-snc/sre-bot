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
    main.main()

    mock_app.assert_called_once_with(token=os.environ.get("SLACK_TOKEN"))

    mock_app.return_value.command.assert_any_call("/atip")
    mock_app.return_value.command.assert_any_call("/aiprp")
    mock_app.return_value.view.assert_any_call("atip_view")
    mock_app.return_value.action.assert_any_call("ati_search_width")
    mock_app.return_value.action.assert_any_call("atip_change_locale")

    mock_app.return_value.command.assert_any_call("/aws")
    mock_app.return_value.view.assert_any_call("aws_access_view")
    mock_app.return_value.view.assert_any_call("aws_health_view")

    mock_app.return_value.command.assert_any_call("/incident")
    mock_app.return_value.view.assert_any_call("incident_view")
    mock_app.return_value.action.assert_any_call("handle_incident_action_buttons")
    mock_app.return_value.action.assert_any_call("incident_change_locale")

    mock_app.return_value.action.assert_any_call("add_folder_metadata")
    mock_app.return_value.action.assert_any_call("view_folder_metadata")
    mock_app.return_value.view.assert_any_call("view_folder_metadata_modal")
    mock_app.return_value.view.assert_any_call("add_metadata_view")
    mock_app.return_value.action.assert_any_call("delete_folder_metadata")
    mock_app.return_value.action.assert_any_call("archive_channel")
    mock_app.return_value.view.assert_any_call("view_save_incident_roles")

    mock_app.return_value.command.assert_any_call("/sre")

    mock_app.return_value.view.assert_any_call("create_webhooks_view")
    mock_app.return_value.action.assert_any_call("toggle_webhook")
    mock_app.return_value.action.assert_any_call("reveal_webhook")

    mock_socket_mode_handler.assert_called_once_with(
        mock_app(), os.environ.get("APP_TOKEN")
    )

    mock_scheduled_tasks.init.assert_called_once_with(mock_app.return_value)
    mock_scheduled_tasks.run_continuously.assert_called_once_with()
