"""Behaviour of the dev incident command handlers when the store is unavailable.

Tests cover the store call of modules/dev/incident.py's list_incidents, which
should catch IncidentStoreUnavailableError and respond appropriately.

Calls use the handlers' real (ack, logger, respond, client, body) signature;
collaborators outside the store boundary (incident_conversation, incident_folder)
are stubbed only as needed to reach each store call cleanly.
"""

from unittest.mock import MagicMock, patch

import pytest

from contracts.operations import OperationStatus
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
