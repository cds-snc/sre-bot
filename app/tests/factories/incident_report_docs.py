"""A stub Google Docs service holding one incident report, for the report timeline tests."""

from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError


def google_http_error(status: int) -> HttpError:
    """Return an ``HttpError`` as the Google client raises it for ``status``."""

    class Response(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=cast("Any", Response()), content=b"{}")


TIMELINE_START = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
TIMELINE_END = "Trigger"


class StubDocs:
    """A Docs service holding one report, ``document_id``, as characters with an optional link.

    ``documents().get`` answers the body as paragraphs of text runs (linked runs carry
    ``textStyle.link.url``) at a revision counter; ``documents().batchUpdate`` applies
    ``deleteContentRange``, ``insertText`` and ``updateTextStyle`` the way Docs does, with
    indexes counted in UTF-16 code units, and refuses with a 400 when
    ``writeControl.requiredRevisionId`` is not the current revision. Any other document is
    a 404. Hooks model a slow or contended API: ``before_write`` runs before the guard,
    ``confirm_write`` returning False raises ``TimeoutError`` after the edit landed, and
    ``fail_write`` (when set) is raised instead of writing.
    """

    def __init__(self, document_id: str = "D0REPORT", timeline: str = "\n") -> None:
        self.document_id = document_id
        self.chars: list[tuple[str, str | None]] = []
        self.revision = 1
        self.write_attempts = 0
        self.reads = 0
        self.before_write: Callable[[], None] = lambda: None
        self.confirm_write: Callable[[], bool] = lambda: True
        self.fail_write: Exception | None = None
        self.unreadable = False
        self.set_timeline(timeline)
        self.service = MagicMock()
        self.service.documents.return_value.get.side_effect = self._get
        self.service.documents.return_value.batchUpdate.side_effect = self._batch_update

    def set_timeline(self, timeline: str, *, before: str = "Timeline\n", after: str = "") -> None:
        """Replace the whole body: ``before``, the start marker, ``timeline``, the end marker, ``after``."""
        self.chars = [(char, None) for char in f"{before}{TIMELINE_START}\n{timeline}{TIMELINE_END}\n{after}"]

    def text(self) -> str:
        return "".join(char for char, _ in self.chars)

    def timeline(self) -> str:
        """Return the plain text between the markers."""
        return self.text().split(TIMELINE_START)[1].split(TIMELINE_END)[0]

    def links(self) -> list[str]:
        """Return the distinct link urls in body order."""
        urls: list[str] = []
        for _, url in self.chars:
            if url and (not urls or urls[-1] != url):
                urls.append(url)
        return urls

    def content(self) -> list[dict[str, Any]]:
        """Return the body as Docs structural elements."""
        paragraphs: list[dict[str, Any]] = []
        elements: list[dict[str, Any]] = []
        run: dict[str, Any] | None = None
        index = 1
        for char, link in self.chars:
            if run is None or run["link"] != link:
                run = {"link": link, "startIndex": index, "text": ""}
                elements.append(run)
            run["text"] += char
            if char == "\n":
                paragraphs.append(self._paragraph(elements))
                elements, run = [], None
            index += _utf16(char)
        if elements:
            paragraphs.append(self._paragraph(elements))
        return paragraphs

    def apply_unguarded(self, requests: list[dict[str, Any]]) -> None:
        """Apply ``requests`` regardless of revision, as an earlier unguarded write would have."""
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

    def _get(self, documentId: str) -> MagicMock:
        request = MagicMock()
        self.reads += 1
        if documentId != self.document_id or self.unreadable:
            request.execute.side_effect = google_http_error(404)
        else:
            request.execute.return_value = {"revisionId": str(self.revision), "body": {"content": self.content()}}
        return request

    def _batch_update(self, documentId: str, body: Any) -> MagicMock:
        request = MagicMock()
        request.execute.side_effect = lambda: self._write(documentId, body)
        return request

    def _write(self, document_id: str, body: Any) -> dict[str, Any]:
        self.write_attempts += 1
        if self.fail_write is not None:
            raise self.fail_write
        if document_id != self.document_id:
            raise google_http_error(404)
        self.before_write()
        if body["writeControl"]["requiredRevisionId"] != str(self.revision):
            raise google_http_error(400)
        self.apply_unguarded(body["requests"])
        if not self.confirm_write():
            raise TimeoutError("unconfirmed")
        return {"replies": []}

    def _offset(self, index: int) -> int:
        units = 1
        for offset, (char, _) in enumerate(self.chars):
            if units == index:
                return offset
            units += _utf16(char)
        assert units == index, "Index must be a UTF-16 character boundary"
        return len(self.chars)

    @staticmethod
    def _paragraph(runs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": run["startIndex"],
                        "endIndex": run["startIndex"] + _utf16(run["text"]),
                        "textRun": {
                            "content": run["text"],
                            "textStyle": {"link": {"url": run["link"]}} if run["link"] else {},
                        },
                    }
                    for run in runs
                ]
            }
        }


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
