"""Unit tests for the incident_draft Slack report-link lookup adapter."""

from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from packages.incident_draft.adapters import slack as slack_adapter
from packages.incident_draft.adapters.slack import SlackIncidentReportLinkLookup, build_incident_report_link_lookup
from packages.incident_draft.service import IncidentReportLinkLookup

pytestmark = pytest.mark.unit

_REPORT_LINK = "https://docs.google.com/document/d/DOC123/edit"


def test_find_report_links_calls_bookmarks_list_and_returns_the_incident_report_links() -> None:
    """Only bookmarks titled "Incident report" count; their links come back as plain strings."""
    client = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {"title": "Some runbook", "link": "https://example.com"},
            {"title": "Incident report", "link": _REPORT_LINK},
        ],
    }

    assert SlackIncidentReportLinkLookup(client).find_report_links("C123") == [_REPORT_LINK]
    client.bookmarks_list.assert_called_once_with(channel_id="C123")


def test_report_links_keep_the_order_slack_listed_them_in() -> None:
    """Several "Incident report" bookmarks are returned in listed order, so the caller's first match is Slack's first."""
    client = MagicMock()
    client.bookmarks_list.return_value = {
        "ok": True,
        "bookmarks": [
            {"title": "Incident report", "link": "https://example.com/first"},
            {"title": "Other", "link": "https://example.com/other"},
            {"title": "Incident report", "link": "https://example.com/second"},
        ],
    }

    assert SlackIncidentReportLinkLookup(client).find_report_links("C123") == [
        "https://example.com/first",
        "https://example.com/second",
    ]


@pytest.mark.parametrize("bookmark", [{"title": "Incident report"}, {"title": "Incident report", "link": None}])
def test_a_report_bookmark_without_a_link_yields_an_empty_string_entry(bookmark: dict[str, str | None]) -> None:
    """A bookmark with no link still counts as an entry, so the caller can report it as unusable."""
    client = MagicMock()
    client.bookmarks_list.return_value = {"ok": True, "bookmarks": [bookmark]}

    assert SlackIncidentReportLinkLookup(client).find_report_links("C123") == [""]


def test_missing_bookmarks_key_yields_no_links() -> None:
    """A response without the expected key reads as empty rather than raising."""
    client = MagicMock()
    client.bookmarks_list.return_value = {"ok": True}

    assert SlackIncidentReportLinkLookup(client).find_report_links("C123") == []


def test_a_slack_api_error_yields_no_links() -> None:
    """The adapter owns the degradation: a Web API error is not raised and reads as no report links."""
    client = MagicMock()
    client.bookmarks_list.side_effect = SlackApiError("err", {"ok": False, "error": "missing_scope"})

    assert SlackIncidentReportLinkLookup(client).find_report_links("C123") == []


def test_build_incident_report_link_lookup_uses_the_bot_web_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The built adapter satisfies the package Protocol and calls through the shared client factory's client."""
    client = MagicMock()
    client.bookmarks_list.return_value = {"ok": True, "bookmarks": [{"title": "Incident report", "link": _REPORT_LINK}]}
    monkeypatch.setattr(slack_adapter, "get_slack_web_client", lambda: client)

    lookup = build_incident_report_link_lookup()

    assert isinstance(lookup, IncidentReportLinkLookup)
    assert lookup.find_report_links("C123") == [_REPORT_LINK]
    client.bookmarks_list.assert_called_once_with(channel_id="C123")
