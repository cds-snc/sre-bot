from commands import incident

from unittest.mock import MagicMock


def test_incident_open_modal_calls_ack():
    ack = MagicMock()
    incident.open_modal(ack)
    ack.assert_called_once()


def test_incident_submit_calls_ack():
    ack = MagicMock()
    incident.submit(ack)
    ack.assert_called_once()
