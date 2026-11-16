"""The incident list sheet's row format and row lookup, shared by the Sheets adapter and its fake.

One row per incident, six columns: A the UTC declared date, B the report as a
``HYPERLINK`` (the plain title without a report), C the product, D the status,
E the channel as a ``HYPERLINK`` (empty without a conversation), F the incident
id, which is the key rows are found by. Columns A-E are the legacy writer's
format byte for byte (``modules/incident/incident_folder.py``). Free text is
never evaluated by the sheet: a plain-text cell starting with a formula
character is written as text, and text placed inside a formula has its quotes
doubled (decisions/workplace-systems.md, rule 5). Pure functions; no I/O.
"""

import re
from collections.abc import Sequence
from datetime import UTC

from features.incident.core.domain import Incident

_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")
_CHANNEL_ID = re.compile(r"(?:[?&]channel=|/archives/)([A-Za-z0-9]+)")


def guard_text(value: str) -> str:
    """Return ``value`` as a plain-text cell: a leading formula character gets a leading apostrophe."""
    return f"'{value}" if value.startswith(_FORMULA_LEADS) else value


def _hyperlink(url: str, label: str) -> str:
    return f'=HYPERLINK("{url.replace(chr(34), chr(34) * 2)}", "{label.replace(chr(34), chr(34) * 2)}")'


def list_row(incident: Incident, *, channel_link: str | None, channel_label: str | None) -> list[str]:
    """Return the incident's six cells; ``channel_link`` and ``channel_label`` are both set or both ``None``."""
    report_url = incident.report.url if incident.report is not None else None
    title = _hyperlink(report_url, incident.title) if report_url else guard_text(incident.title)
    channel = _hyperlink(channel_link, f"#{channel_label}") if channel_link and channel_label is not None else ""
    return [
        incident.declared_at.astimezone(UTC).strftime("%Y-%m-%d"),
        title,
        guard_text(incident.product or ""),
        incident.status.value,
        channel,
        incident.id,
    ]


def channel_id_from_row_formula(formula: str) -> str | None:
    """Return the Slack channel id in a channel cell's link (``app_redirect?channel=`` or ``/archives/``), else ``None``."""
    match = _CHANNEL_ID.search(formula)
    return match.group(1) if match else None


def row_index_for(incident_id: str, channel_id: str | None, rows: Sequence[Sequence[str]]) -> tuple[int, bool] | None:
    """Find the incident's row among the E:F ``rows`` (the header is row 1).

    Returns the 1-based sheet row and whether it matched through the channel
    fallback, or ``None``. A row whose F is the id wins; otherwise the first row
    with an empty F whose channel cell names ``channel_id``.
    """
    fallback: int | None = None
    for number, cells in enumerate(rows, start=1):
        key = cells[1] if len(cells) > 1 else ""
        if key == incident_id:
            return number, False
        if fallback is None and channel_id and not key and cells and channel_id_from_row_formula(cells[0]) == channel_id:
            fallback = number
    return (fallback, True) if fallback is not None else None
