"""Timeline saves from the floppy-disk reaction, run against an in-memory Google Doc.

The Docs adapter seam (fetch_document_snapshot / apply_document_edits) is replaced by a
fake that applies batchUpdate requests to real text and enforces the required revision
the way the Docs API does, so the tests assert on what ends up in the document.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters.google_docs import DocumentSnapshot
from features.incident.response.settings import IncidentResponseSettings
from modules.incident import incident_conversation, incident_document
from modules.incident.incident_document import END_HEADING, START_HEADING

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

    def apply_edits(self, _document_id: str, requests: list[dict], required_revision_id: str) -> OperationResult[None]:
        self.write_attempts += 1
        self.before_write()
        if required_revision_id != str(self.revision):
            return OperationResult.transient_error("Stale revision", error_code="DOCUMENT_REVISION_CONFLICT")
        self.apply_unguarded(requests)
        if self.confirm_write():
            return OperationResult.success()
        return OperationResult.transient_error("Unconfirmed write", error_code=ErrorCode.TIMEOUT)

    def apply_unguarded(self, requests: list[dict]) -> None:
        for request in requests:
            if "deleteContentRange" in request:
                span = request["deleteContentRange"]["range"]
                del self.chars[self._offset(span["startIndex"]) : self._offset(span["endIndex"])]
            elif "insertText" in request:
                index = self._offset(request["insertText"]["location"]["index"])
                self.chars[index:index] = [(char, None) for char in request["insertText"]["text"]]
            elif "updateTextStyle" in request:
                span = request["updateTextStyle"]["range"]
                url = request["updateTextStyle"]["textStyle"].get("link", {}).get("url")
                for index in range(self._offset(span["startIndex"]), self._offset(span["endIndex"])):
                    self.chars[index] = (self.chars[index][0], url)
        self.revision += 1

    def _offset(self, index: int) -> int:
        units = 1
        for offset, (char, _) in enumerate(self.chars):
            if units == index:
                return offset
            units += len(char.encode("utf-16-le")) // 2
        assert units == index, "Index must be a UTF-16 character boundary"
        return len(self.chars)

    def timeline(self) -> str:
        text = "".join(char for char, _ in self.chars)
        return text.split(START_HEADING)[1].split(END_HEADING)[0]

    def _content(self) -> list[dict]:
        paragraphs: list[dict] = []
        elements: list[dict] = []
        run: dict | None = None
        index = 1
        for char, link in self.chars:
            if run is None or run["link"] != link:
                run = {"link": link, "startIndex": index, "text": ""}
                elements.append(run)
            run["text"] += char
            if char == "\n":
                paragraphs.append(self._paragraph(elements))
                elements, run = [], None
            index += len(char.encode("utf-16-le")) // 2
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
                        "endIndex": run["startIndex"] + len(run["text"].encode("utf-16-le")) // 2,
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
        patch.object(incident_document, "sleep"),
        patch.object(
            incident_document,
            "get_incident_response_settings",
            return_value=IncidentResponseSettings(),
            create=True,
        ),
    ):
        yield fake


def _slack_client(ts: str, text: str) -> MagicMock:
    client = MagicMock()
    client.conversations_info.return_value = {"channel": {"name": "incident-2026-10-01-test"}}
    client.conversations_history.return_value = {
        "messages": [{"ts": ts, "user": "U123", "text": text}],
        "has_more": False,
    }
    client.reactions_get.return_value = {
        "ok": True,
        "type": "message",
        "message": {"ts": ts, "user": "U123", "text": text},
    }
    client.chat_getPermalink.return_value = {"permalink": PERMALINK.format(ts.replace(".", ""))}
    client.users_profile_get.return_value = {"profile": {"real_name": "Jane Doe"}}
    return client


def _react(handler, ts: str, text: str, *, name: str = "Jane Doe") -> MagicMock:
    body = {"event": {"user": "UACTOR", "reaction": "floppy_disk", "item": {"type": "message", "channel": "C123", "ts": ts}}}
    client = _slack_client(ts, text)
    client.users_profile_get.return_value = {"profile": {"real_name": name}}
    with (
        patch.object(incident_conversation, "get_incident_document_id", return_value="document-id"),
        patch.object(incident_conversation.slack_users, "replace_user_id_with_handle", lambda _client, message: message),
    ):
        handler(client, lambda: None, body)
    return client


def _save(ts: str, text: str) -> None:
    _react(incident_conversation.handle_reaction_added, ts, text)


def _unsave(ts: str, text: str) -> None:
    _react(incident_conversation.handle_reaction_removed, ts, text)


def _write_four_times_from_one_read(document: FakeDocument, ts: str, text: str) -> None:
    """Leave the document as four unguarded saves of one message built from the same read would."""
    captured: list[list[dict]] = []
    with patch.object(
        incident_document,
        "apply_document_edits",
        lambda _id, requests, _rev: captured.append(requests) or OperationResult.success(),
    ):
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

    assert not updated.is_success
    assert document.write_attempts == IncidentResponseSettings().timeline_update_attempts
    assert "note" not in document.timeline()


def test_update_reports_failure_without_writing_when_document_cannot_be_read():
    """A classified read failure surfaces as no snapshot; nothing is written."""
    with (
        patch.object(incident_document, "fetch_document_snapshot", return_value=None),
        patch.object(incident_document, "apply_document_edits") as apply_document_edits,
    ):
        updated = incident_document.update_timeline_section("document-id", lambda content: content)

    assert not updated.is_success
    apply_document_edits.assert_not_called()


def test_update_reports_failure_without_writing_when_timeline_headings_are_missing():
    """A document without the timeline placeholder headings is left untouched."""
    snapshot = DocumentSnapshot(content=[{"paragraph": {"elements": [{"textRun": {"content": "no headings"}}]}}], revision_id="1")
    with (
        patch.object(incident_document, "fetch_document_snapshot", return_value=snapshot),
        patch.object(incident_document, "apply_document_edits") as apply_document_edits,
    ):
        updated = incident_document.update_timeline_section("document-id", lambda content: content)

    assert not updated.is_success
    apply_document_edits.assert_not_called()


@pytest.mark.parametrize("name", ["Anne-Marie", "O'Neil", "J. Smith", "Alice (Ops)", "Élodie"])
def test_late_save_preserves_punctuated_names_and_sorts_entries(document, name):
    """Names are display content, not delimiters that can hide an earlier entry."""
    _save("1759435380.000200", "later")
    _react(incident_conversation.handle_reaction_added, "1759435320.000100", "earlier", name=name)
    timeline = document.timeline()
    assert name in timeline
    assert timeline.index("earlier") < timeline.index("later")


def test_distinct_messages_in_same_second_are_both_saved(document):
    """Full Slack timestamps distinguish messages even when their displayed times match."""
    _save("1759435320.000200", "second")
    _save("1759435320.000100", "first")
    _save("1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    assert document.timeline().count("second") == 1
    assert document.timeline().index("first") < document.timeline().index("second")


def test_empty_timeline_accepts_first_message(document):
    """A section with adjacent boundary paragraphs accepts its first capture."""
    document.chars = [(c, None) for c in f"{START_HEADING}\n{END_HEADING}\n"]
    _save("1759435320.000100", "first")
    assert document.timeline().count("first") == 1


def test_multiline_inline_arrow_and_manual_text_survive_rewrite(document):
    """A save preserves leading manual notes, inline arrows, and complete multiline messages."""
    at = "".join(c for c, _ in document.chars).index(END_HEADING)
    document.chars[at:at] = [(c, None) for c in "Manual note\n"]
    _save("1759435320.000100", "first ➡️ still first\ncontinuation")
    _save("1759435380.000200", "second")
    assert "Manual note" in document.timeline()
    assert "first ➡️ still first\ncontinuation" in document.timeline()
    assert document.timeline().count("second") == 1


def test_remove_uses_identity_after_profile_or_message_edit(document):
    """Unsaving removes the stored message even after text and profile names change."""
    _save("1759435320.000100", "original")
    _react(incident_conversation.handle_reaction_removed, "1759435320.000100", "edited", name="New Name")
    assert "original" not in document.timeline()


def test_emoji_body_uses_utf16_indexes_and_preserves_links(document):
    """Supplementary characters do not shift subsequent entries or their hyperlinks."""
    _save("1759435320.000100", "first 😀")
    _save("1759435380.000200", "second")
    assert "first 😀" in document.timeline()
    assert "second" in document.timeline()
    assert any(line.endswith("Jane Doe: first 😀") for line in document.timeline().splitlines())
    assert any(line.endswith("Jane Doe: second") for line in document.timeline().splitlines())
    extracted = incident_document.extract_timeline_section(document._content())
    assert PERMALINK.format("1759435320000100") in extracted
    assert PERMALINK.format("1759435380000200") in extracted


def test_thread_reaction_saves_reply_not_parent(document):
    """The reaction's item is resolved directly, without interpreting history pagination as a thread."""
    client = _react(incident_conversation.handle_reaction_added, "1759435320.000100", "reply")
    assert "reply" in document.timeline()
    client.reactions_get.assert_called_once_with(channel="C123", timestamp="1759435320.000100")
    client.conversations_history.assert_not_called()
    client.conversations_replies.assert_not_called()


@pytest.mark.parametrize("handler", [incident_conversation.handle_reaction_added, incident_conversation.handle_reaction_removed])
def test_retry_exhaustion_notifies_actor_for_add_and_remove(document, handler):
    """A contended write reports failure privately to the reacting user, never as success."""
    _save("1759435320.000100", "first")
    document.before_write = lambda: setattr(document, "revision", document.revision + 1)
    ts = "1759435380.000200" if handler is incident_conversation.handle_reaction_added else "1759435320.000100"
    client = _react(handler, ts, "first")
    notice = client.chat_postEphemeral.call_args.kwargs
    assert notice["user"] == "UACTOR"
    assert notice["channel"] == "C123"
    assert "could not" in notice["text"].lower()
    assert "retry" in notice["text"].lower()


def test_two_distinct_interleaved_saves_both_survive(document):
    """A competing save between snapshot and write is retained when the losing writer retries."""
    ran = False

    def compete():
        nonlocal ran
        if not ran:
            ran = True
            _save("1759435380.000200", "second")

    document.before_write = compete
    _save("1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    assert document.timeline().count("second") == 1


def test_contended_save_succeeds_after_three_rejections(document):
    """Contention beyond the former three attempts can recover after a fresh read and backoff."""

    def compete():
        if document.write_attempts <= 3:
            document.revision += 1

    document.before_write = compete
    client = _react(incident_conversation.handle_reaction_added, "1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    assert document.write_attempts == 4
    client.chat_postEphemeral.assert_not_called()
    assert incident_document.sleep.call_count == 3


def test_final_unconfirmed_write_is_reconciled_without_duplicate(document):
    """A write that lands on the last allowed attempt is confirmed by a final snapshot."""
    limit = IncidentResponseSettings().timeline_update_attempts
    document.before_write = lambda: setattr(document, "revision", document.revision + (document.write_attempts < limit))
    document.confirm_write = lambda: False
    client = _react(incident_conversation.handle_reaction_added, "1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    assert document.write_attempts == limit
    client.chat_postEphemeral.assert_not_called()


@pytest.mark.parametrize(
    ("result", "attempts", "wait"),
    [
        (OperationResult.error(OperationStatus.UNAUTHORIZED, "Forbidden", error_code="403"), 1, None),
        (OperationResult.transient_error("Rate limited", error_code="429", retry_after=60), 1, None),
        (OperationResult.transient_error("Rate limited", error_code="429", retry_after=1), 2, 1),
    ],
)
def test_permanent_and_rate_limit_errors_bound_inline_retry(document, result, attempts, wait):
    """Permanent errors stop, short Retry-After hints are honored, and long hints are not shortened."""
    with patch.object(incident_document, "apply_document_edits", side_effect=[result, OperationResult.success()]) as edit:
        _react(incident_conversation.handle_reaction_added, "1759435320.000100", "first")
    assert edit.call_count == attempts
    if wait is None:
        incident_document.sleep.assert_not_called()
    else:
        assert incident_document.sleep.call_args.args[0] >= wait


@pytest.mark.parametrize(
    "response",
    [
        {"ok": True, "type": "message", "message": {"ts": "different", "text": "wrong"}},
        {"ok": True, "type": "file"},
        {"ok": False, "error": "message_not_found"},
    ],
)
def test_mismatched_or_missing_message_is_not_saved_and_notifies_user(document, response):
    """Slack lookup failures never substitute a nearby message or silently acknowledge a capture."""
    client = _slack_client("1759435320.000100", "first")
    client.reactions_get.return_value = response
    body = {"event": {"user": "UACTOR", "item": {"type": "message", "channel": "C123", "ts": "1759435320.000100"}}}
    incident_conversation.handle_reaction_added(client, lambda: None, body)
    assert document.write_attempts == 0
    client.chat_postEphemeral.assert_called_once()


def test_failure_notice_error_is_logged(document):
    """An unavailable Slack notification is logged rather than hiding a failed capture."""
    client = _slack_client("1759435320.000100", "first")
    client.reactions_get.return_value = {"ok": False, "error": "message_not_found"}
    client.chat_postEphemeral.side_effect = SlackApiError("failed", {"error": "channel_not_found"})
    body = {"event": {"user": "UACTOR", "item": {"channel": "C123", "ts": "1759435320.000100"}}}
    with patch.object(incident_conversation, "logger") as log:
        incident_conversation.handle_reaction_added(client, lambda: None, body)
    assert any(call.args[0] == "incident_timeline_notice_failed" for call in log.error.call_args_list)


def test_dst_fallback_sorts_by_message_instant_not_displayed_clock(document):
    """Repeated Eastern clock times still sort by the Slack message's absolute timestamp."""
    earlier = f"{int(datetime.fromisoformat('2026-11-01T05:59:00+00:00').timestamp())}.000100"
    later = f"{int(datetime.fromisoformat('2026-11-01T06:01:00+00:00').timestamp())}.000100"
    _save(later, "later")
    _save(earlier, "earlier")
    assert document.timeline().index("earlier") < document.timeline().index("later")


def test_permalink_query_variants_do_not_duplicate_or_prevent_removal(document):
    """Thread query parameters are not part of the underlying message identity."""
    _save("1759435320.000100", "first")
    document.chars = [(char, f"{link}?thread_ts=1759435000.000001&cid=C123" if link else None) for char, link in document.chars]
    _save("1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    _unsave("1759435320.000100", "edited")
    assert "first" not in document.timeline()


def test_concurrent_human_edit_survives_retry(document):
    """A human note added after the read is incorporated rather than overwritten on retry."""
    ran = False

    def human_edit():
        nonlocal ran
        if not ran:
            ran = True
            at = "".join(c for c, _ in document.chars).index(END_HEADING)
            document.chars[at:at] = [(c, None) for c in "Human note\n"]
            document.revision += 1

    document.before_write = human_edit
    _save("1759435320.000100", "first")
    assert "Human note" in document.timeline()
    assert document.timeline().count("first") == 1


def test_unconfirmed_write_and_failed_reconciliation_reports_uncertain_outcome(document):
    """An unreadable confirmation does not claim that a possibly landed edit was rejected."""

    def fetch(_id):
        return None if document.write_attempts else document.fetch_snapshot(_id)

    document.confirm_write = lambda: False
    with patch.object(incident_document, "fetch_document_snapshot", fetch):
        client = _react(incident_conversation.handle_reaction_added, "1759435320.000100", "first")
    assert document.timeline().count("first") == 1
    assert "could not confirm" in client.chat_postEphemeral.call_args.kwargs["text"].lower()


def test_non_text_timeline_content_is_not_destructively_rewritten(document):
    """Tables and inline objects cannot be represented losslessly as timeline text."""
    snapshot = document.fetch_snapshot("doc")
    snapshot.content.insert(2, {"table": {}, "startIndex": len(START_HEADING) + 10})
    with patch.object(incident_document, "fetch_document_snapshot", return_value=snapshot):
        client = _react(incident_conversation.handle_reaction_added, "1759435320.000100", "first")
    assert document.write_attempts == 0
    client.chat_postEphemeral.assert_called_once()


@pytest.mark.parametrize("handler", [incident_conversation.handle_reaction_added, incident_conversation.handle_reaction_removed])
def test_channel_lookup_failure_notifies_reacting_user(document, handler):
    """A failed Slack channel read is still an explicitly failed capture after acknowledgement."""
    client = _slack_client("1759435320.000100", "first")
    client.conversations_info.side_effect = SlackApiError("failed", {"error": "channel_not_found"})
    body = {"event": {"user": "UACTOR", "item": {"channel": "C123", "ts": "1759435320.000100"}}}
    handler(client, lambda: None, body)
    assert document.write_attempts == 0
    client.chat_postEphemeral.assert_called_once()


def test_styled_date_split_across_text_runs_keeps_message_identity(document):
    """Bold or other styles can split one linked date without changing which message it identifies."""
    _save("1759435320.000100", "first")

    def fetch(_id):
        snapshot = document.fetch_snapshot(_id)
        for paragraph in snapshot.content:
            runs = paragraph["paragraph"]["elements"]
            for index, run in enumerate(runs):
                if run["textRun"]["textStyle"].get("link"):
                    split = 10
                    runs[index : index + 1] = [
                        {
                            **run,
                            "endIndex": run["startIndex"] + split,
                            "textRun": {
                                **run["textRun"],
                                "content": run["textRun"]["content"][:split],
                            },
                        },
                        {
                            **run,
                            "startIndex": run["startIndex"] + split,
                            "textRun": {
                                **run["textRun"],
                                "content": run["textRun"]["content"][split:],
                            },
                        },
                    ]
                    break
        return snapshot

    with patch.object(incident_document, "fetch_document_snapshot", fetch):
        _save("1759435320.000100", "first")
    assert document.timeline().count("first") == 1
