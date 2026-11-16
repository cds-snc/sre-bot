"""One behaviour suite for every IncidentListProjection: the Google Sheets adapter and the in-memory fake.

The adapter runs over a stateful Sheets stand-in at the gateway factory with
stubbed settings; the fake is built bare and its rows are read from itself. Each
test runs against both, so a consumer tested on the fake sees the adapter's
rules: a repeated ``append_row`` converges on one row, ``update_status`` on an
unknown incident writes that incident's full row with the status, two incidents
are two rows, and the rows are those ``list_rows`` builds.
"""

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters import slack
from features.incident.core.adapters.google_sheets import GoogleSheetsIncidentListProjection
from features.incident.core.adapters.in_memory import InMemoryIncidentListProjection
from features.incident.core.adapters.list_rows import list_row
from features.incident.core.api import IncidentListProjection
from tests.factories.incident_list_sheet import CHANNEL_LINK, FakeSheetsService, install_sheet, listed_incident

pytestmark = pytest.mark.unit


@dataclass
class Subject:
    projection: IncidentListProjection
    rows: Callable[[], list[list[str]]]


def _adapter(monkeypatch: pytest.MonkeyPatch) -> Subject:
    sheet = FakeSheetsService()
    install_sheet(monkeypatch, sheet)
    return Subject(GoogleSheetsIncidentListProjection(), sheet.data_rows)


def _fake(monkeypatch: pytest.MonkeyPatch) -> Subject:
    monkeypatch.setattr(slack, "get_slack_settings", lambda: SimpleNamespace(tenant=SimpleNamespace(team_id="T0SLACK")))
    fake = InMemoryIncidentListProjection()
    return Subject(fake, lambda: fake.rows)


@pytest.fixture(params=[_adapter, _fake], ids=["google_sheets", "in_memory"])
def subject(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Subject:
    build: Callable[[pytest.MonkeyPatch], Subject] = request.param
    return build(monkeypatch)


def test_both_implementations_satisfy_the_protocol(subject: Subject) -> None:
    """Consumers type against the Protocol; the adapter and the fake are runtime instances of it."""
    assert isinstance(subject.projection, IncidentListProjection)


async def test_appending_twice_leaves_one_row(subject: Subject) -> None:
    """A retried or repeated append converges: the incident has one row."""
    incident = listed_incident()

    first = await subject.projection.append_row(incident)
    second = await subject.projection.append_row(incident)

    assert first.status is second.status is OperationStatus.SUCCESS
    assert len(subject.rows()) == 1


async def test_status_update_of_an_unknown_incident_writes_its_row(subject: Subject) -> None:
    """A missing row is re-written in full, carrying the status asked for."""
    incident = listed_incident()

    result = await subject.projection.update_status(incident, IncidentStatus.CLOSED)

    assert result.status is OperationStatus.SUCCESS
    assert subject.rows() == [
        list_row(
            listed_incident(status=IncidentStatus.CLOSED), channel_link=CHANNEL_LINK, channel_label="2026-10-01-database-outage"
        )
    ]


async def test_status_update_changes_only_the_status_of_an_existing_row(subject: Subject) -> None:
    """After an append, the status update leaves one row with the new status in D."""
    incident = listed_incident()
    await subject.projection.append_row(incident)

    await subject.projection.update_status(incident, IncidentStatus.REVIEWED)

    (row,) = subject.rows()
    assert row[3] == "Reviewed"
    assert row[5] == "id-1"


async def test_two_incidents_are_two_rows(subject: Subject) -> None:
    """Rows are keyed by incident id: another incident never overwrites the first."""
    await subject.projection.append_row(listed_incident("id-1"))
    await subject.projection.append_row(listed_incident("id-2", channel="C999"))

    assert [row[5] for row in subject.rows()] == ["id-1", "id-2"]
