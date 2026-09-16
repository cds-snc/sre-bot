"""Behaviour of the dev incident command handlers when the store is unavailable.

Tests cover the four surface sites in modules/dev/incident.py (list_incidents,
load_incidents, add_incident twice for different calls). Each handler should
catch IncidentStoreUnavailableError and respond appropriately.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations import OperationStatus
from modules.dev import incident
from modules.incident import db_operations


@pytest.mark.unit
@patch("modules.dev.incident.db_operations")
def test_list_incidents_responds_when_store_unavailable(mock_db_ops):
    """When the incidents store is unavailable, the handler responds with the unavailable message."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.list_incidents.side_effect = db_operations.IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR)

    respond = MagicMock()

    incident.list_incidents(respond)

    respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.incident_folder")
def test_load_incidents_responds_when_store_unavailable(mock_incident_folder):
    """When the incidents store is unavailable during batch import, the handler responds."""
    mock_incident_folder.create_missing_incidents.side_effect = db_operations.IncidentStoreUnavailableError(
        OperationStatus.PERMANENT_ERROR
    )

    respond = MagicMock()
    test_incidents = [
        {
            "channel_id": "C001",
            "channel_name": "incident-test-1",
            "name": "Test 1",
            "user_id": "U001",
            "teams": [],
            "report_url": "http://example.com",
            "meet_url": "http://example.com",
        },
    ]

    with patch("modules.dev.incident.db_operations") as mock_db_ops:
        mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
        mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE

        incident.load_incidents(test_incidents, respond)

        respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.db_operations")
def test_add_incident_responds_when_get_incident_by_channel_id_store_unavailable(mock_db_ops):
    """When get_incident_by_channel_id raises, the handler responds with the unavailable message."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.get_incident_by_channel_id.side_effect = db_operations.IncidentStoreUnavailableError(
        OperationStatus.PERMANENT_ERROR
    )

    respond = MagicMock()

    incident.add_incident("C001", respond)

    respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)


@pytest.mark.unit
@patch("modules.dev.incident.db_operations")
def test_add_incident_responds_when_create_incident_store_unavailable(mock_db_ops):
    """When create_incident raises via duplicate check, the handler responds."""
    mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError
    mock_db_ops.INCIDENT_STORE_UNAVAILABLE_MESSAGE = db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE
    mock_db_ops.get_incident_by_channel_id.return_value = None  # No existing incident
    mock_db_ops.create_incident.side_effect = db_operations.IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR)

    respond = MagicMock()

    incident.add_incident("C001", respond)

    respond.assert_called_once_with(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)
