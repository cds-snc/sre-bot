"""Slack adapter — implements ``IncidentReportLinkLookup`` on the Slack Web API.

Incident channels carry an "Incident report" bookmark pointing at the report
document. The adapter owns the degradation: a Web API failure is logged here
and never raised.
"""

import structlog
from slack_sdk import WebClient

from integrations.slack.client import get_slack_web_client

logger = structlog.get_logger()

_INCIDENT_REPORT_BOOKMARK = "Incident report"


class SlackIncidentReportLinkLookup:
    """Find an incident channel's report links among its Slack bookmarks."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def find_report_links(self, conversation_id: str) -> list[str]:
        """Return the links of the channel's "Incident report" bookmarks, in listed order.

        A bookmark without a link is an empty string. On any Slack API failure
        of ``bookmarks.list`` no links are returned, so the caller renders its
        no-document path.
        """
        try:
            response = self._client.bookmarks_list(channel_id=conversation_id)
        except Exception as exc:  # noqa: BLE001 - degrade to "no document" on any API error
            logger.warning("incident_draft_bookmarks_fetch_failed", conversation_id=conversation_id, error=str(exc))
            return []

        bookmarks = response.get("bookmarks") or []
        return [str(bookmark.get("link") or "") for bookmark in bookmarks if bookmark.get("title") == _INCIDENT_REPORT_BOOKMARK]


def build_incident_report_link_lookup() -> SlackIncidentReportLinkLookup:
    """Build the adapter on the bot's Web client."""
    return SlackIncidentReportLinkLookup(get_slack_web_client())
