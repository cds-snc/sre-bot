import json
from unittest.mock import MagicMock, patch
import uuid
from modules.incident import information_update


@patch("modules.incident.information_update.logging")
@patch("modules.incident.information_update.update_field_view")
def test_open_update_field_view(mock_update_field_view, mock_logging):
    mock_client = MagicMock()
    mock_respond = MagicMock()
    private_metadata = json.dumps({"status": "data"})
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345", "private_metadata": private_metadata},
        "actions": [
            {"action_id": "update_incident_field", "value": "action_to_perform"}
        ],
    }
    mock_update_field_view.return_value = {"view": [{"block": "block_id"}]}
    information_update.open_update_field_view(mock_client, body, mock_respond)
    mock_update_field_view.assert_called_once_with(
        "action_to_perform", {"status": "data"}
    )
    mock_client.views_push.assert_called_once_with(
        trigger_id="T12345",
        view_id="V12345",
        view={"view": [{"block": "block_id"}]},
    )


@patch("modules.incident.information_update.logging")
def test_update_field_view(mock_logging):
    view = information_update.update_field_view("status", {"status": "data"})
    mock_logging.info.assert_called_once_with(
        "Loading Update Field View for action: %s", "status"
    )
    assert view == {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "status",
                    "emoji": True,
                },
            }
        ],
    }


@patch("modules.incident.information_update.logging")
def test_update_field_view_date_field(mock_logging):
    incident_data = {"status": "data", "detection_time": "1234567890"}
    view = information_update.update_field_view("detection_time", incident_data)
    mock_logging.info.assert_called_once_with(
        "Loading Update Field View for action: %s", "detection_time"
    )
    assert view == {
        "type": "modal",
        "callback_id": "update_field_modal",
        "title": {
            "type": "plain_text",
            "text": "Incident Information",
            "emoji": True,
        },
        "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": json.dumps(
            {"action": "detection_time", "incident_data": incident_data}
        ),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "detection_time",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "date_input",
                "element": {
                    "type": "datepicker",
                    "initial_date": "2009-02-13",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a date",
                    },
                    "action_id": "date_picker",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select a date",
                },
            },
            {
                "type": "input",
                "block_id": "time_input",
                "element": {
                    "type": "timepicker",
                    "initial_time": "23:31",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select time",
                        "emoji": True,
                    },
                    "action_id": "time_picker",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select time",
                    "emoji": True,
                },
            },
        ],
    }


@patch("modules.incident.information_display.incident_information_view")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission(
    mock_db_operations, mock_incident_information_view
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_logger = MagicMock()
    # update value as a string based on date and time input 2024-01-12 12:00
    updated_value = "1705060800.0"
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "date_input": {"date_picker": {"selected_date": "2024-01-12"}},
                "time_input": {"time_picker": {"selected_time": "12:00"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "detection_time",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}

    information_update.handle_update_field_submission(
        mock_client, body, mock_ack, view, mock_logger
    )
    mock_db_operations.update_incident_field.assert_called_once_with(
        mock_logger,
        incident_data["id"],
        "detection_time",
        updated_value,
        incident_data["user_id"],
        type="S",
    )
    mock_client.chat_postMessage.assert_called_once_with(
        channel=incident_data["channel_id"],
        text="<@user_id> has updated the field detection_time to 2024-01-12 12:00",
    )


@patch("modules.incident.information_display.incident_information_view")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_not_supported(
    mock_db_operations, mock_incident_information_view
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    mock_logger = MagicMock()
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "date_input": {"date_picker": {"selected_date": "2024-01-12"}},
                "time_input": {"time_picker": {"selected_time": "12:00"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "unsupported_field",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}

    information_update.handle_update_field_submission(
        mock_client, body, mock_ack, view, mock_logger
    )
    mock_db_operations.update_incident_field.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()
    mock_incident_information_view.assert_not_called()
    mock_client.views_update.assert_not_called()
    mock_logger.error.assert_called_once_with("Unknown action: %s", "unsupported_field")


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
