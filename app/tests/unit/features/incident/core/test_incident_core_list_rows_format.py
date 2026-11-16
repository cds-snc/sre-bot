"""The incident list row: columns A-E as the legacy writer wrote them, column F the incident id.

Pure functions, no stubs. The pinned values are what ``add_new_incident_to_list``
wrote for the same inputs (date, ``=HYPERLINK`` report, product, status,
``=HYPERLINK`` channel), so people and formulas reading the sheet see no change.
Free text is never evaluated by the sheet: a plain-text cell starting with a
formula character (or its full-width form) is written with a leading apostrophe,
and text inside a ``HYPERLINK`` string has its quotes doubled. The row lookup
reads the E:F values and prefers an id match over the channel-id fallback.
"""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.list_rows import channel_id_from_row_formula, guard_text, list_row, row_index_for
from tests.factories.incident_list_sheet import CHANNEL_FORMULA, CHANNEL_LINK, REPORT_FORMULA, REPORT_URL, listed_incident

pytestmark = pytest.mark.unit


def _row(**kwargs: object) -> list[str]:
    incident = listed_incident(**kwargs)  # type: ignore[arg-type]
    return list_row(
        incident, channel_link=CHANNEL_LINK if incident.conversation else None, channel_label="2026-10-01-database-outage"
    )


def test_row_matches_the_legacy_writer_and_ends_with_the_incident_id() -> None:
    """Columns A-E are the legacy values byte for byte; F carries the id."""
    assert _row() == ["2026-10-01", REPORT_FORMULA, "Notify", "In Progress", CHANNEL_FORMULA, "id-1"]


@pytest.mark.parametrize("status", list(IncidentStatus))
def test_status_cell_is_the_stored_status_string(status: IncidentStatus) -> None:
    """Column D is the status value, whatever the status."""
    assert _row(status=status)[3] == status.value


def test_date_is_the_utc_day_of_the_declaration() -> None:
    """A declaration late in the evening in another zone still dates by UTC."""
    late = datetime(2026, 10, 1, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    incident = dataclasses.replace(listed_incident(), declared_at=late)

    assert late.astimezone(UTC).day == 2
    assert list_row(incident, channel_link=None, channel_label=None)[0] == "2026-10-02"


def test_incident_without_report_conversation_or_product_gets_blank_and_plain_cells() -> None:
    """Missing parts are blank cells or the plain title, never a refusal."""
    row = _row(report=False, channel=None, product=None)

    assert row == ["2026-10-01", "Database outage", "", "In Progress", "", "id-1"]


@pytest.mark.parametrize("lead", ["=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠"])
def test_plain_text_starting_with_a_formula_character_is_written_as_text(lead: str) -> None:
    """Each OWASP leading character, and the full-width forms, gets a leading apostrophe."""
    assert guard_text(f"{lead}SUM(A1)") == f"'{lead}SUM(A1)"


@pytest.mark.parametrize("text", ["Database outage", "", "a=b", "Notify-2", " =spaced"])
def test_other_text_is_unchanged(text: str) -> None:
    """Only a leading character matters; the rest of the text is left as typed."""
    assert guard_text(text) == text


def test_guard_applies_to_the_plain_title_and_the_product() -> None:
    """The cells that are plain text (title without a report, product) are guarded."""
    row = _row(report=False, product="=cmd()", title="@evil")

    assert row[1] == "'@evil"
    assert row[2] == "'=cmd()"


def test_quotes_inside_a_hyperlink_are_doubled() -> None:
    """A title cannot close the formula's string: its quotes are doubled."""
    row = _row(title='say "hi"')

    assert row[1] == f'=HYPERLINK("{REPORT_URL}", "say ""hi""")'


@pytest.mark.parametrize(
    ("formula", "channel_id"),
    [
        (CHANNEL_FORMULA, "C123"),
        ('=HYPERLINK("https://slack.com/app_redirect?channel=C9Z&team=T1", "#x")', "C9Z"),
        ('=HYPERLINK("https://slack.com/app_redirect?team=T1&channel=C9Z", "#x")', "C9Z"),
        ('=HYPERLINK("https://example.slack.com/archives/C777", "#x")', "C777"),
        ("#plain", None),
        ("", None),
    ],
)
def test_channel_id_is_read_from_the_channel_formula(formula: str, channel_id: str | None) -> None:
    """Both link forms the sheet has held carry the channel id; anything else has none."""
    assert channel_id_from_row_formula(formula) == channel_id


HEADER = ["Channel", "Incident id"]


def test_row_is_found_by_the_incident_id() -> None:
    """The first row whose F is the id is the incident's; the number is 1-based sheet rows."""
    rows = [HEADER, [CHANNEL_FORMULA, "other"], ["", "id-1"]]

    assert row_index_for("id-1", "C123", rows) == (3, False)


def test_row_without_an_id_is_found_by_its_channel_id() -> None:
    """A legacy row (empty F) whose E formula names the channel is the fallback match."""
    rows = [HEADER, [CHANNEL_FORMULA]]

    assert row_index_for("id-1", "C123", rows) == (2, True)


def test_fallback_never_takes_a_row_that_has_another_id() -> None:
    """A row keyed by another incident is not the channel's row, even on the same channel."""
    rows = [HEADER, [CHANNEL_FORMULA, "other"]]

    assert row_index_for("id-1", "C123", rows) is None


def test_id_match_wins_over_an_earlier_fallback_row() -> None:
    """A later row keyed by the id beats an earlier unkeyed row of the same channel."""
    rows = [HEADER, [CHANNEL_FORMULA], [CHANNEL_FORMULA, "id-1"]]

    assert row_index_for("id-1", "C123", rows) == (3, False)


def test_no_match_and_no_channel() -> None:
    """No id, and no channel to fall back on, means no row."""
    assert row_index_for("id-1", "C123", [HEADER, ["", "x"]]) is None
    assert row_index_for("id-1", None, [HEADER, [CHANNEL_FORMULA]]) is None
