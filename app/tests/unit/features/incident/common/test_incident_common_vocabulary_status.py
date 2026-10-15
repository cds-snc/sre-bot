"""Unit tests for the incident lifecycle status vocabulary.

Plain value tests: the five stored status strings and which of them count as
open. Every status except Closed is open, so a reviewed but unclosed incident
is still open.
"""

import pytest

from features.incident.common.vocabulary import IncidentStatus

pytestmark = pytest.mark.unit


def test_the_status_values_are_the_stored_strings() -> None:
    """Values match the strings the legacy incidents table already stores."""
    assert [status.value for status in IncidentStatus] == [
        "Open",
        "In Progress",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]


@pytest.mark.parametrize(
    "status",
    [IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS, IncidentStatus.READY_TO_BE_REVIEWED, IncidentStatus.REVIEWED],
)
def test_every_status_except_closed_is_open(status: IncidentStatus) -> None:
    """An incident stays open until it is closed, whatever its review state."""
    assert status.is_open is True


def test_closed_is_not_open() -> None:
    """Closed is the only status that is not open."""
    assert IncidentStatus.CLOSED.is_open is False
