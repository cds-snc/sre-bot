import os
import main

from unittest.mock import patch


@patch("main.SocketModeHandler")
@patch("main.App")
def test_main_invokes_socket_handler(mock_app, mock_socket_mode_handler):
    main.main()

    mock_app.assert_called_once_with(token=os.environ.get("SLACK_TOKEN"))

    mock_app.return_value.command.assert_any_call("/incident")
    mock_app.return_value.view.assert_any_call("incident_view")
    mock_app.return_value.action.assert_any_call("handle_incident_action_buttons")

    mock_app.return_value.command.assert_any_call("/sre")

    mock_app.return_value.view.assert_any_call("create_webhooks_view")
    mock_app.return_value.action.assert_any_call("toggle_webhook")
    mock_app.return_value.action.assert_any_call("reveal_webhook")

    mock_socket_mode_handler.assert_called_once_with(
        mock_app(), os.environ.get("APP_TOKEN")
    )
