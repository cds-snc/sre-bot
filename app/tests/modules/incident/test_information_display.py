import json
from unittest.mock import MagicMock, patch
import uuid
from models.incidents import Incident
from modules.incident import information_display


@patch("modules.incident.information_display.incident_information_view")
@patch("modules.incident.information_display.db_operations")
def test_open_incident_info_view(mock_db_operations, mock_incident_information_view):
    mock_client = MagicMock()
    mock_respond = MagicMock()
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345"},
    }
    mock_db_operations.get_incident_by_channel_id.return_value = {
        "id": {"S": "incident-2024-01-12-test"},
        "channel_id": {"S": "C1234567890"},
        "channel_name": {"S": "incident-2024-01-12-test"},
        "name": {"S": "Test Incident"},
        "user_id": {"S": "U12345"},
        "teams": {"L": [{"S": "team1"}, {"S": "team2"}]},
        "report_url": {"S": "http://example.com/report"},
        "status": {"S": "Open"},
        "meet_url": {"S": "http://example.com/meet"},
        "created_at": {"S": "1234567890"},
        "incident_commander": {"S": "Commander"},
        "operations_lead": {"S": "Lead"},
        "severity": {"S": "High"},
        "start_impact_time": {"S": "1234567890"},
        "end_impact_time": {"S": "1234567890"},
        "detection_time": {"S": "1234567890"},
        "retrospective_url": {"S": "http://example.com/retrospective"},
        "environment": {"S": "prod"},
        "logs": {"L": []},
        "incident_updates": {"L": []},
    }

    incident_data = {
        "id": "incident-2024-01-12-test",
        "channel_id": "C1234567890",
        "channel_name": "incident-2024-01-12-test",
        "name": "Test Incident",
        "user_id": "U12345",
        "teams": ["team1", "team2"],
        "report_url": "http://example.com/report",
        "status": "Open",
        "meet_url": "http://example.com/meet",
        "created_at": "1234567890",
        "incident_commander": "Commander",
        "operations_lead": "Lead",
        "severity": "High",
        "start_impact_time": "1234567890",
        "end_impact_time": "1234567890",
        "detection_time": "1234567890",
        "retrospective_url": "http://example.com/retrospective",
        "environment": "prod",
        "logs": [],
        "incident_updates": [],
    }

    mock_incident_information_view.return_value = {"view": [{"block": "block_id"}]}
    information_display.open_incident_info_view(mock_client, body, mock_respond)
    mock_client.views_open.assert_called_once_with(
        trigger_id="T12345",
        view={"view": [{"block": "block_id"}]},
    )
    mock_incident_information_view.assert_called_once_with(Incident(**incident_data))


@patch("modules.incident.information_display.db_operations")
def test_open_incident_view_no_incident_found(mock_db_operations):
    mock_client = MagicMock()
    mock_respond = MagicMock()
    body = {
        "channel_id": "C12345",
        "channel_name": "incident-2024-01-12-test",
        "user_id": "U12345",
        "trigger_id": "T12345",
        "view": {"id": "V12345"},
    }
    mock_db_operations.get_incident_by_channel_id.return_value = []
    information_display.open_incident_info_view(mock_client, body, mock_respond)
    mock_respond.assert_called_once_with(
        "This is command is only available in incident channels. No incident records found for this channel."
    )


@patch("modules.incident.incident_helper.convert_timestamp")
def test_incident_information_view(mock_convert_timestamp):
    incident_data = generate_incident_data(
        start_impact_time="1234567890",
        end_impact_time="1234567890",
        detection_time="1234567890",
    )
    id = incident_data["id"]
    mock_convert_timestamp.side_effect = [
        "2009-02-13 23:31:30",
        "Unknown",
        "Unknown",
        "Unknown",
    ]
    incident = Incident(**incident_data)
    private_metadata = json.dumps(incident.model_dump())
    view = information_display.incident_information_view(incident)
    assert view == {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {
            "type": "plain_text",
            "text": "Incident Information",
            "emoji": True,
        },
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": private_metadata,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "name",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ID*: " + id,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*:\nstatus",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "status",
                    "action_id": "update_incident_field",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Time Created*:\n2009-02-13 23:31:30",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Detection Time*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "detection_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Start of Impact*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "start_impact_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*End of Impact*:\nUnknown",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "end_impact_time",
                    "action_id": "update_incident_field",
                },
            },
        ],
    }


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
