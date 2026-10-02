"""Timeline saves from the floppy-disk reaction, run against an in-memory Google Doc.

The Docs adapter seam (fetch_document_snapshot / apply_document_edits) is replaced by a
fake that applies batchUpdate requests to real text and enforces the required revision
the way the Docs API does, so the tests assert on what ends up in the document.
"""

from unittest.mock import MagicMock, patch

import pytest

from modules.incident import incident_conversation, incident_document
from modules.incident.incident_document import END_HEADING, START_HEADING
from packages.incident.documents.adapters.google_docs import DocumentSnapshot

PERMALINK = "https://example.slack.com/archives/C123/p{}"


class FakeDocument:
    """A Google Doc reduced to characters with an optional link, plus a revision counter."""

    def __init__(self) -> None:
        self.chars: list[tuple[str, str | None]] = [(char, None) for char in f"Timeline\n{START_HEADING}\n\n{END_HEADING}\n"]
        self.revision = 1
        self.write_attempts = 0
        # Hooks let a test model a slow or contended Docs API.
        self.before_write = lambda: None
        self.confirm_write = lambda: True

    def fetch_snapshot(self, _document_id: str) -> DocumentSnapshot:
        return DocumentSnapshot(content=self._content(), revision_id=str(self.revision))

    def apply_edits(self, _document_id: str, requests: list[dict], required_revision_id: str) -> bool:
        self.write_attempts += 1
        self.before_write()
        if required_revision_id != str(self.revision):
            return False
        self.apply_unguarded(requests)
        return self.confirm_write()

    def apply_unguarded(self, requests: list[dict]) -> None:
        for request in requests:
            if "deleteContentRange" in request:
                span = request["deleteContentRange"]["range"]
                del self.chars[span["startIndex"] - 1 : span["endIndex"] - 1]
            elif "insertText" in request:
                index = request["insertText"]["location"]["index"] - 1
                self.chars[index:index] = [(char, None) for char in request["insertText"]["text"]]
            elif "updateTextStyle" in request:
                span = request["updateTextStyle"]["range"]
                url = request["updateTextStyle"]["textStyle"]["link"]["url"]
                for index in range(span["startIndex"] - 1, span["endIndex"] - 1):
                    self.chars[index] = (self.chars[index][0], url)
        self.revision += 1

    def timeline(self) -> str:
        text = "".join(char for char, _ in self.chars)
        return text.split(START_HEADING)[1].split(END_HEADING)[0]

    def _content(self) -> list[dict]:
        paragraphs: list[dict] = []
        elements: list[dict] = []
        run: dict | None = None
        for index, (char, link) in enumerate(self.chars, start=1):
            if run is None or run["link"] != link:
                run = {"link": link, "startIndex": index, "text": ""}
                elements.append(run)
            run["text"] += char
            if char == "\n":
                paragraphs.append(self._paragraph(elements))
                elements, run = [], None
        if elements:
            paragraphs.append(self._paragraph(elements))
        return paragraphs

    @staticmethod
    def _paragraph(runs: list[dict]) -> dict:
        return {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": run["startIndex"],
                        "endIndex": run["startIndex"] + len(run["text"]),
                        "textRun": {
                            "content": run["text"],
                            "textStyle": {"link": {"url": run["link"]}} if run["link"] else {},
                        },
                    }
                    for run in runs
                ]
            }
        }


@pytest.fixture
def document():
    fake = FakeDocument()
    with (
        patch.object(incident_document, "fetch_document_snapshot", fake.fetch_snapshot),
        patch.object(incident_document, "apply_document_edits", fake.apply_edits),
    ):
        yield fake


def _slack_client(ts: str, text: str) -> MagicMock:
    client = MagicMock()
    client.conversations_info.return_value = {"channel": {"name": "incident-2026-10-01-test"}}
    client.conversations_history.return_value = {
        "messages": [{"ts": ts, "user": "U123", "text": text}],
        "has_more": False,
    }
    client.chat_getPermalink.return_value = {"permalink": PERMALINK.format(ts.replace(".", ""))}
    client.users_profile_get.return_value = {"profile": {"real_name": "Jane Doe"}}
    return client


def _react(handler, ts: str, text: str) -> None:
    body = {"event": {"reaction": "floppy_disk", "item": {"channel": "C123", "ts": ts}}}
    with (
        patch.object(incident_conversation, "get_incident_document_id", return_value="document-id"),
        patch.object(incident_conversation.slack_users, "replace_user_id_with_handle", lambda _client, message: message),
    ):
        handler(_slack_client(ts, text), lambda: None, body)


def _save(ts: str, text: str) -> None:
    _react(incident_conversation.handle_reaction_added, ts, text)


def _unsave(ts: str, text: str) -> None:
    _react(incident_conversation.handle_reaction_removed, ts, text)


def _write_four_times_from_one_read(document: FakeDocument, ts: str, text: str) -> None:
    """Leave the document as four unguarded saves of one message built from the same read would."""
    captured: list[list[dict]] = []
    with patch.object(incident_document, "apply_document_edits", lambda _id, requests, _rev: captured.append(requests) or True):
        _save(ts, text)
    for _ in range(4):
        document.apply_unguarded(captured[0])


def test_saved_messages_are_written_once_in_chronological_order(document):
    """Each save reads the document once and lands one entry; saving again changes nothing."""
    _save("1759435380.000200", "second message")
    _save("1759435320.000100", "first message")
    _save("1759435320.000100", "first message")

    timeline = document.timeline()
    assert timeline.count("first message") == 1
    assert timeline.count("second message") == 1
    assert timeline.index("first message") < timeline.index("second message")
    assert document.write_attempts == 2


def test_write_that_times_out_after_landing_is_not_written_again(document):
    """An unconfirmed write is followed by a new read, which finds the entry and stops."""
    document.confirm_write = lambda: False

    _save("1759435320.000100", "first message")

    assert document.timeline().count("first message") == 1
    assert document.write_attempts == 1


def test_edit_built_from_a_stale_read_is_rejected_instead_of_duplicating(document):
    """A competing save of the same message lands between this save's read and its write."""
    competitor_ran = False

    def competing_save_lands_first():
        nonlocal competitor_ran
        if not competitor_ran:
            competitor_ran = True
            _save("1759435320.000100", "first message")

    document.before_write = competing_save_lands_first

    _save("1759435320.000100", "first message")

    assert document.timeline().count("first message") == 1


def test_next_save_collapses_entries_duplicated_by_earlier_stale_writes(document):
    """Rewriting the section keeps one entry per Slack message, so the next save repairs it."""
    _write_four_times_from_one_read(document, "1759435320.000100", "first message")
    assert document.timeline().count("first message") == 4

    _save("1759435380.000200", "second message")

    timeline = document.timeline()
    assert timeline.count("first message") == 1
    assert timeline.count("second message") == 1


def test_removing_the_reaction_removes_every_copy_of_the_entry(document):
    """Unsaving a duplicated message clears all of its copies and leaves other entries alone."""
    _save("1759435320.000100", "first message")
    _write_four_times_from_one_read(document, "1759435380.000200", "second message")
    assert document.timeline().count("second message") == 4

    _unsave("1759435380.000200", "second message")

    timeline = document.timeline()
    assert "second message" not in timeline
    assert timeline.count("first message") == 1


def test_update_gives_up_after_bounded_attempts_when_no_write_is_confirmed(document):
    """Every write is rejected, so the update stops after the attempt limit and reports failure."""
    document.before_write = lambda: setattr(document, "revision", document.revision + 1)

    updated = incident_document.update_timeline_section("document-id", lambda content: content + " ➡️ note")

    assert updated is False
    assert document.write_attempts == incident_document.TIMELINE_UPDATE_ATTEMPTS
    assert "note" not in document.timeline()


def test_update_reports_failure_without_writing_when_document_cannot_be_read():
    """A classified read failure surfaces as no snapshot; nothing is written."""
    with (
        patch.object(incident_document, "fetch_document_snapshot", return_value=None),
        patch.object(incident_document, "apply_document_edits") as apply_document_edits,
    ):
        updated = incident_document.update_timeline_section("document-id", lambda content: content)

    assert updated is False
    apply_document_edits.assert_not_called()


def test_update_reports_failure_without_writing_when_timeline_headings_are_missing():
    """A document without the timeline placeholder headings is left untouched."""
    snapshot = DocumentSnapshot(content=[{"paragraph": {"elements": [{"textRun": {"content": "no headings"}}]}}], revision_id="1")
    with (
        patch.object(incident_document, "fetch_document_snapshot", return_value=snapshot),
        patch.object(incident_document, "apply_document_edits") as apply_document_edits,
    ):
        updated = incident_document.update_timeline_section("document-id", lambda content: content)

    assert updated is False
    apply_document_edits.assert_not_called()
