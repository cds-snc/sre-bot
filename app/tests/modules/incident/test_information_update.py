from datetime import datetime
import json
from unittest.mock import MagicMock, patch
import uuid
from modules.incident import information_update


@patch("modules.incident.information_update.update_field_view")
def test_open_update_field_view(mock_update_field_view):
    mock_client = MagicMock()
    mock_ack = MagicMock()
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
    information_update.open_update_field_view(mock_client, body, mock_ack)
    mock_update_field_view.assert_called_once_with(
        mock_client, body, "action_to_perform", {"status": "data"}
    )
    mock_client.views_push.assert_called_once_with(
        trigger_id="T12345",
        view_id="V12345",
        view={"view": [{"block": "block_id"}]},
    )


@patch("modules.incident.information_update.generate_default_field_update_view")
@patch("modules.incident.information_update.logger")
def test_update_field_view_default(
    mock_logger, mock_generate_default_field_update_view
):
    mock_client = MagicMock()
    body = {
        "channel_id": "C12345",
    }
    information_update.update_field_view(
        mock_client, body, "some_action", {"some_action": "data"}
    )
    mock_logger.info.assert_called_once_with(
        "updating_field_view",
        field="some_action",
        incident_data={"some_action": "data"},
    )
    mock_generate_default_field_update_view.assert_called_once_with("some_action")


def test_generate_default_field_update_view():
    view = information_update.generate_default_field_update_view("some_action")
    assert view == {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "some_action",
                    "emoji": True,
                },
            }
        ],
    }


@patch("modules.incident.information_update.generate_date_field_update_view")
@patch("modules.incident.information_update.datetime")
@patch("modules.incident.information_update.utils")
@patch("modules.incident.information_update.logger")
def test_update_field_view_date_field(
    mock_logger, mock_utils, mock_datetime, mock_generate_date_field_update_view
):
    mock_client = MagicMock()
    body = {
        "channel_id": "C12345",
        "user": {"id": "U12345"},
    }
    incident_data = {"status": "data", "detection_time": "1234567890"}
    mock_client.users_info.return_value = {"user": {"tz": "America/Montreal"}}
    mock_datetime.datetime.now.return_value = mock_datetime.datetime(
        2009, 2, 13, 23, 31, 0
    )
    mock_datetime.datetime.now.return_value.strftime.side_effect = [
        "2009-02-13",
        "23:31",
    ]
    # mock_datetime.strftime.side_effect = ["2009-02-13", "23:31"]
    mock_utils.convert_utc_datetime_to_tz.return_value = "2009-02-13 23:31"
    information_update.update_field_view(
        mock_client, body, "detection_time", incident_data
    )
    mock_logger.info.assert_called_once_with(
        "updating_field_view",
        field="detection_time",
        incident_data={"status": "data", "detection_time": "1234567890"},
    )
    mock_generate_date_field_update_view.assert_called_once_with(
        mock_client, body, "detection_time", incident_data
    )


@patch("modules.incident.information_update.utils")
@patch("modules.incident.information_update.datetime")
def test_generate_date_field_update_view(mock_datetime, mock_utils):
    incident_data = {"status": "data", "detection_time": "1234567890"}
    body = {
        "channel_id": "C12345",
        "user": {"id": "U12345"},
    }
    mock_client = MagicMock()
    mock_client.users_info.return_value = {"user": {"tz": "America/Montreal"}}

    mock_date = MagicMock()
    mock_date.strftime.side_effect = ["2009-02-13", "18:31"]
    mock_datetime.now.return_value = mock_date
    mock_datetime.fromtimestamp.return_value = mock_date

    mock_converted_date = MagicMock()
    mock_converted_date.strftime.side_effect = ["2009-02-13", "23:31"]
    mock_utils.convert_utc_datetime_to_tz.return_value = mock_converted_date

    view = information_update.generate_date_field_update_view(
        mock_client, body, "detection_time", incident_data
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
    mock_client.users_info.assert_called_once_with(user="U12345")
    mock_utils.convert_utc_datetime_to_tz.assert_called_with(
        mock_datetime.fromtimestamp.return_value, "America/Montreal"
    )


@patch("modules.incident.information_update.generate_text_field_update_view")
@patch("modules.incident.information_update.logger")
def test_update_field_view_text_field(
    mock_logger, mock_generate_text_field_update_view
):
    mock_client = MagicMock()
    body = {
        "channel_id": "C12345",
    }
    incident_data = {"status": "data", "retrospective_url": "unknown"}
    information_update.update_field_view(
        mock_client, body, "retrospective_url", incident_data
    )
    mock_logger.info.assert_called_once_with(
        "updating_field_view",
        field="retrospective_url",
        incident_data={"status": "data", "retrospective_url": "unknown"},
    )
    mock_generate_text_field_update_view.assert_called_once_with(
        "retrospective_url", incident_data
    )


def test_generate_text_field_update_view():
    incident_data = {"status": "data", "retrospective_url": "unknown"}
    view = information_update.generate_text_field_update_view(
        "retrospective_url", incident_data
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
            {"action": "retrospective_url", "incident_data": incident_data}
        ),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "retrospective_url",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "plain_text_input",
                "element": {
                    "type": "plain_text_input",
                    "initial_value": "unknown",
                    "action_id": "text_input",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Enter text",
                },
            },
        ],
    }


@patch(
    "modules.incident.information_update.FIELD_SCHEMA",
    new={"status": {"type": "dropdown", "options": ["Open", "Closed"]}},
)
@patch("modules.incident.information_update.generate_drop_down_field_update_view")
@patch("modules.incident.information_update.logger")
def test_update_field_view_dropdown_field(
    mock_logger, mock_generate_drop_down_field_update_view
):
    mock_client = MagicMock()
    body = {
        "channel_id": "C12345",
    }
    incident_data = {"status": "Open", "retrospective_url": "unknown"}
    information_update.update_field_view(mock_client, body, "status", incident_data)
    mock_logger.info.assert_called_once_with(
        "updating_field_view", field="status", incident_data=incident_data
    )
    mock_generate_drop_down_field_update_view.assert_called_once_with(
        "status", incident_data, ["Open", "Closed"]
    )


@patch(
    "modules.incident.information_update.FIELD_SCHEMA",
    new={"status": {"type": "dropdown", "options": ["Open", "Closed"]}},
)
def test_generate_drop_down_field_update_view():
    incident_data = {"status": "Open", "retrospective_url": "unknown"}
    view = information_update.generate_drop_down_field_update_view(
        "status", incident_data, ["Open", "Closed"]
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
            {"action": "status", "incident_data": incident_data}
        ),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "status",
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "drop_down_input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an item",
                    },
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Open"},
                        "value": "Open",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Open"},
                            "value": "Open",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Closed"},
                            "value": "Closed",
                        },
                    ],
                    "action_id": "static_select",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select an item",
                },
            },
        ],
    }


@patch("modules.incident.information_update.logger")
@patch("modules.incident.information_update.datetime")
@patch("modules.incident.information_update.utils")
@patch("modules.incident.information_update.incident_document")
@patch("modules.incident.information_update.incident_folder")
@patch("modules.incident.information_update.information_display")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_date_type(
    mock_db_operations,
    mock_information_display,
    mock_incident_folder,
    mock_incident_document,
    mock_utils,
    mock_datetime,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
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
    mock_client.users_info.return_value = {"user": {"tz": "America/Montreal"}}
    mock_datetime.strptime.return_value = datetime(2024, 1, 12, 12, 0)
    mock_utils.convert_tz_datetime_to_utc.return_value = datetime.fromtimestamp(
        float(updated_value)
    )
    mock_information_display.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }

    information_update.handle_update_field_submission(mock_client, body, mock_ack, view)
    mock_db_operations.update_incident_field.assert_called_once_with(
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
    mock_incident_document.update_incident_document_status.assert_not_called()
    mock_incident_folder.update_spreadsheet_incident_status.assert_not_called()


@patch("modules.incident.information_update.logger")
@patch("modules.incident.information_update.incident_document")
@patch("modules.incident.information_update.incident_folder")
@patch("modules.incident.information_update.information_display")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_text_type(
    mock_db_operations,
    mock_information_display,
    mock_incident_folder,
    mock_incident_document,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "plain_text_input": {"text_input": {"value": "new_value"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "retrospective_url",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_information_display.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }

    information_update.handle_update_field_submission(mock_client, body, mock_ack, view)
    mock_db_operations.update_incident_field.assert_called_once_with(
        incident_data["id"],
        "retrospective_url",
        "new_value",
        incident_data["user_id"],
        type="S",
    )
    mock_client.chat_postMessage.assert_called_once_with(
        channel=incident_data["channel_id"],
        text="<@user_id> has updated the field retrospective_url to new_value",
    )
    mock_incident_document.update_incident_document_status.assert_not_called()
    mock_incident_folder.update_spreadsheet_incident_status.assert_not_called()


@patch("modules.incident.information_update.logger")
@patch("modules.incident.information_update.google_docs")
@patch("modules.incident.information_update.incident_document")
@patch("modules.incident.information_update.incident_folder")
@patch("modules.incident.information_update.information_display")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_dropdown_type(
    mock_db_operations,
    mock_information_display,
    mock_incident_folder,
    mock_incident_document,
    mock_google_docs,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "drop_down_input": {
                    "static_select": {"selected_option": {"value": "Closed"}}
                }
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "status",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_google_docs.extract_google_doc_id.return_value = "document_id"
    mock_information_display.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }

    information_update.handle_update_field_submission(mock_client, body, mock_ack, view)
    mock_db_operations.update_incident_field.assert_called_once_with(
        incident_data["id"],
        "status",
        "Closed",
        incident_data["user_id"],
        type="S",
    )
    mock_client.chat_postMessage.assert_called_once_with(
        channel=incident_data["channel_id"],
        text="<@user_id> has updated the field status to Closed",
    )
    mock_google_docs.extract_google_doc_id.assert_called_once_with("report_url")
    mock_incident_document.update_incident_document_status.assert_called_once_with(
        "document_id", "Closed"
    )
    mock_incident_folder.update_spreadsheet_incident_status.assert_called_once_with(
        incident_data["channel_name"], "Closed"
    )


@patch("modules.incident.information_update.logger")
@patch("modules.incident.information_update.incident_document")
@patch("modules.incident.information_update.incident_folder")
@patch("modules.incident.information_update.information_display")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_not_supported(
    mock_db_operations,
    mock_information_display,
    mock_incident_folder,
    mock_incident_document,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
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
    mock_information_display.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }

    information_update.handle_update_field_submission(mock_client, body, mock_ack, view)
    mock_db_operations.update_incident_field.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()
    mock_information_display.incident_information_view.assert_not_called()
    mock_client.views_update.assert_not_called()
    mock_logger.error.assert_called_once_with(
        "update_field_submission",
        action="unsupported_field",
        message="Unsupported action type",
    )
    mock_incident_document.update_incident_document_status.assert_not_called()
    mock_incident_folder.update_spreadsheet_incident_status.assert_not_called()


@patch(
    "modules.incident.information_update.FIELD_SCHEMA",
    new={"status": {"type": "some_type"}},
)
@patch("modules.incident.information_update.logger")
@patch("modules.incident.information_update.incident_document")
@patch("modules.incident.information_update.incident_folder")
@patch("modules.incident.information_update.information_display")
@patch("modules.incident.information_update.db_operations")
def test_handle_update_field_submission_with_unknown_type(
    mock_db_operations,
    mock_incident_information_display,
    mock_incident_folder,
    mock_incident_document,
    mock_logger,
):
    mock_client = MagicMock()
    mock_ack = MagicMock()
    incident_data = generate_incident_data()
    view = {
        "state": {
            "values": {
                "plain_text_input": {"text_input": {"value": "new_value"}},
            }
        },
        "private_metadata": json.dumps(
            {
                "action": "status",
                "incident_data": incident_data,
            }
        ),
    }
    body = {
        "user": {"id": incident_data["user_id"]},
        "view": {"root_view_id": "root_view_id"},
    }
    mock_incident_information_display.incident_information_view.return_value = {
        "view": [{"block": "block_id"}]
    }

    information_update.handle_update_field_submission(mock_client, body, mock_ack, view)
    mock_logger.error.assert_called_once_with(
        "update_field_submission", action="status", message="Unsupported action type"
    )
    mock_db_operations.update_incident_field.assert_not_called()
    mock_client.chat_postMessage.assert_not_called()
    mock_incident_information_display.incident_information_view.assert_not_called()
    mock_client.views_update.assert_not_called()
    mock_incident_document.update_incident_document_status.assert_not_called()
    mock_incident_folder.update_spreadsheet_incident_status.assert_not_called()


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
