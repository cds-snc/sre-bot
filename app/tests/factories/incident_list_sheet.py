"""A stateful stand-in for the Google Sheets values API holding the incident list sheet.

``FakeSheetsService`` answers the four calls the incident list projection makes
(``get``, ``update``, ``batchUpdate``, ``append`` on ``spreadsheets().values()``)
over an in-memory grid of six-column rows, and records every request with its
keyword arguments, the ``num_retries`` its ``execute`` received and the thread it
ran on.
"""

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters import google_sheets, slack
from features.incident.core.domain import ConversationReference, Incident, ReportReference

COLUMNS = 6
HEADER = ["Date", "Incident", "Product", "Status", "Channel", "Incident id"]


@dataclass
class Request:
    """One recorded request: the method, its keyword arguments, execute's retries and the thread."""

    method: str
    kwargs: dict[str, Any]
    num_retries: int | None = None
    thread: int = 0


@dataclass
class _Pending:
    run: Callable[[], dict[str, Any]]
    request: Request
    log: list[Request] = field(default_factory=list)

    def execute(self, num_retries: int | None = None) -> dict[str, Any]:
        self.request.num_retries = num_retries
        self.request.thread = threading.get_ident()
        self.log.append(self.request)
        return self.run()


class FakeSheetsService:
    """The Sheets service surface the projection uses, over ``rows`` (the header row is row 1)."""

    def __init__(self, rows: list[list[str]] | None = None) -> None:
        self.rows: list[list[str]] = [list(HEADER)] + [_padded(row) for row in rows or []]
        self.requests: list[Request] = []

    def spreadsheets(self) -> FakeSheetsService:
        return self

    def values(self) -> FakeSheetsService:
        return self

    def _pending(self, method: str, kwargs: dict[str, Any], run: Callable[[], dict[str, Any]]) -> _Pending:
        return _Pending(run=run, request=Request(method=method, kwargs=kwargs), log=self.requests)

    def get(self, **kwargs: Any) -> _Pending:
        def run() -> dict[str, Any]:
            return {"values": [_trimmed(row[4:6]) for row in self.rows]}

        return self._pending("get", kwargs, run)

    def update(self, **kwargs: Any) -> _Pending:
        def run() -> dict[str, Any]:
            self._set(kwargs["range"], kwargs["body"]["values"])
            return {}

        return self._pending("update", kwargs, run)

    def batchUpdate(self, **kwargs: Any) -> _Pending:  # noqa: N802 - the Sheets API's name
        def run() -> dict[str, Any]:
            for entry in kwargs["body"]["data"]:
                self._set(entry["range"], entry["values"])
            return {}

        return self._pending("batchUpdate", kwargs, run)

    def append(self, **kwargs: Any) -> _Pending:
        def run() -> dict[str, Any]:
            self.rows.extend(_padded(row) for row in kwargs["body"]["values"])
            return {}

        return self._pending("append", kwargs, run)

    def _set(self, a1_range: str, values: list[list[str]]) -> None:
        match = re.fullmatch(r"Sheet1!([A-F])(\d+)(?::([A-F])\d+)?", a1_range)
        assert match is not None, a1_range
        column, row = ord(match.group(1)) - ord("A"), int(match.group(2)) - 1
        for offset, value in enumerate(values[0]):
            self.rows[row][column + offset] = value

    def data_rows(self) -> list[list[str]]:
        """Every row below the header."""
        return self.rows[1:]

    def sent(self, method: str) -> list[Request]:
        """The recorded requests of one method."""
        return [request for request in self.requests if request.method == method]


def _padded(row: list[str]) -> list[str]:
    return [*row, *([""] * (COLUMNS - len(row)))]


def _trimmed(cells: list[str]) -> list[str]:
    trimmed = list(cells)
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


SHEET_ID = "SHEET-ID-SECRET"
REPORT_URL = "https://docs.google.com/document/d/abc/edit"
CHANNEL_LINK = "https://slack.com/app_redirect?channel=C123&team=T0SLACK"
CHANNEL_FORMULA = f'=HYPERLINK("{CHANNEL_LINK}", "#2026-10-01-database-outage")'
REPORT_FORMULA = f'=HYPERLINK("{REPORT_URL}", "Database outage")'


def listed_incident(
    incident_id: str = "id-1",
    *,
    title: str = "Database outage",
    status: IncidentStatus = IncidentStatus.IN_PROGRESS,
    product: str | None = "Notify",
    channel: str | None = "C123",
    report: bool = True,
) -> Incident:
    """An incident declared 2026-10-01 12:00 UTC, with a Slack channel, report and product unless left out."""
    return Incident(
        id=incident_id,
        title=title,
        status=status,
        declared_by="U0DECLARER",
        declared_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        security_incident=False,
        product=product,
        conversation=ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id=channel)
        if channel
        else None,
        report=ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="abc", url=REPORT_URL)
        if report
        else None,
    )


def install_sheet(
    monkeypatch: pytest.MonkeyPatch,
    service: FakeSheetsService,
    *,
    sheet_id: str = SHEET_ID,
    google_tenant: bool = True,
    team_id: str | None = "T0SLACK",
) -> MagicMock:
    """Replace the gateway factory, the settings getters and the Slack tenant; return the factory mock."""
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_sheets, "get_sheets_service", factory)
    tenant = SimpleNamespace(customer_id="C0GOOGLE") if google_tenant else None
    monkeypatch.setattr(google_sheets, "get_google_workspace_settings", lambda: SimpleNamespace(tenant=tenant))
    monkeypatch.setattr(google_sheets, "get_incident_core_settings", lambda: SimpleNamespace(list_sheet_id=sheet_id))
    slack_tenant = SimpleNamespace(team_id=team_id) if team_id is not None else None
    monkeypatch.setattr(slack, "get_slack_settings", lambda: SimpleNamespace(tenant=slack_tenant))
    return factory
