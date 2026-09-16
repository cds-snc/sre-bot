"""Behaviour of the dev incident command handlers when the store is unavailable.

Tests cover the four surface sites in modules/dev/incident.py (list_incidents,
load_incidents, add_incident twice for different calls). Each handler should
catch IncidentStoreUnavailableError and respond appropriately.

Calls use the handlers' real (ack, logger, respond, client, body) signature;
collaborators outside the store boundary (incident_conversation, incident_folder)
are stubbed only as needed to reach each store call cleanly.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations import OperationStatus
from modules.dev import incident
from modules.incident import db_operations


@pytest.mark.unit
@patch("modules.dev.incident.incident_conversation")
@patch("modules.dev.incident.db_operations")
def test_list_incidents_responds_when_store_unavailable(mock_db_ops, mock_incident_conversation):
    """When list_incidents raises, the handler responds with the unavailable message."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.list_incidents.side_effect = db_operations.IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR)
    mock_incident_conversation.is_incident_channel.return_value = (True, False)

    ack = MagicMock()
    logger = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = {"channel_id": "C001"}

    incident.list_incidents(ack, logger, respond, client, body)

    respond.assert_called_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.incident_folder")
def test_load_incidents_responds_when_store_unavailable(mock_incident_folder):
    """When create_missing_incidents raises during batch import, the handler responds."""
    mock_incident_folder.get_incidents_from_sheet.return_value = []
    mock_incident_folder.complete_incidents_details.return_value = []
    mock_incident_folder.create_missing_incidents.side_effect = db_operations.IncidentStoreUnavailableError(
        OperationStatus.PERMANENT_ERROR
    )

    ack = MagicMock()
    logger = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = {}

    with patch("modules.dev.incident.db_operations") as mock_db_ops:
        mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
        mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE

        incident.load_incidents(ack, logger, respond, client, body)

        respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.incident_conversation")
@patch("modules.dev.incident.db_operations")
def test_add_incident_responds_when_get_incident_by_channel_id_store_unavailable(mock_db_ops, mock_incident_conversation):
    """When get_incident_by_channel_id raises, the handler responds with the unavailable message."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.get_incident_by_channel_id.side_effect = db_operations.IncidentStoreUnavailableError(
        OperationStatus.PERMANENT_ERROR
    )
    mock_incident_conversation.is_incident_channel.return_value = (True, True)

    ack = MagicMock()
    logger = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = {"channel_id": "C001"}

    incident.add_incident(ack, logger, respond, client, body)

    respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.incident_folder")
@patch("modules.dev.incident.incident_conversation")
@patch("modules.dev.incident.db_operations")
def test_add_incident_responds_when_create_incident_store_unavailable(
    mock_db_ops, mock_incident_conversation, mock_incident_folder
):
    """When create_incident raises, the handler responds."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.get_incident_by_channel_id.return_value = None  # No existing incident
    mock_db_ops.create_incident.side_effect = db_operations.IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR)
    mock_incident_conversation.is_incident_channel.return_value = (True, True)
    mock_incident_folder.get_incident_details.return_value = {
        "channel_id": "C001",
        "channel_name": "incident-dev-c001",
        "name": "Incident: Test",
        "user_id": "U001",
        "teams": ["Development"],
        "created_at": "1234567890",
        "report_url": "http://example.com/report",
        "meet_url": "http://example.com/meet",
    }

    ack = MagicMock()
    logger = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {"id": "C001", "name": "incident-dev-c001", "topic": {"value": "Incident: Test"}, "created": "1234567890"},
    }
    body = {"channel_id": "C001", "user_id": "U001"}

    incident.add_incident(ack, logger, respond, client, body)

    respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)
