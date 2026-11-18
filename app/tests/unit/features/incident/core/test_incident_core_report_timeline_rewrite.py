"""The report timeline's pure text rewrites in the Google Docs adapter.

Each function is called directly on hand-built Docs structural elements or timeline
text, with nothing patched: reading the section between the markers (lossless, links
rendered as markdown, refused on content it cannot round-trip), locating the markers'
indexes, building the batchUpdate that replaces the section (indexes in UTF-16 code
units), the identity of an entry (channel and full Slack ts from the permalink), the
chronological sort, and the add and remove rewrites the reaction handlers and the
report port both run. Assertions are on returned text and request indexes, the values
Docs consumes.
"""

from datetime import datetime
from typing import Any

import pytest

from features.incident.core.adapters.google_docs import (
    TIMELINE_END_HEADING,
    TIMELINE_START_HEADING,
    build_timeline_replacement,
    extract_timeline_section,
    find_heading_indices,
    rearrange_by_datetime_ascending,
    timeline_message_key,
    timeline_with_entry,
    timeline_without_entry,
)

pytestmark = pytest.mark.unit

START = TIMELINE_START_HEADING
END = TIMELINE_END_HEADING
PERMALINK = "https://example.slack.com/archives/C123/p{}"


def _paragraphs(*items: str | dict[str, Any]) -> list[dict[str, Any]]:
    return [item if isinstance(item, dict) else {"paragraph": {"elements": [{"textRun": {"content": item}}]}} for item in items]


def _indexed(*texts: str) -> list[dict[str, Any]]:
    """Paragraphs of one run each, with the start and end indexes Docs reports (UTF-16, from 1)."""
    content: list[dict[str, Any]] = []
    index = 1
    for text in texts:
        end = index + len(text.encode("utf-16-le")) // 2
        content.append({"paragraph": {"elements": [{"startIndex": index, "endIndex": end, "textRun": {"content": text}}]}})
        index = end
    return content


def _entry(ts: str, text: str, when: str = "2026-10-02 16:02:00") -> str:
    return f"\n ➡️ [{when} ET]({PERMALINK.format(ts.replace('.', ''))}) Jane Doe: {text}\n"


def test_the_markers_are_the_report_template_lines() -> None:
    """The template and every existing report hold these exact lines, so they never change."""
    assert START == "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
    assert END == "Trigger"


@pytest.mark.parametrize(
    "content",
    [
        [START, "Timeline content", END],
        ["Some text", START, "Timeline content", END],
        [START, "Timeline content", END, "Some text"],
        ["Start of some text", START, "Timeline content", END, "End of some text"],
    ],
)
def test_extract_returns_only_the_text_between_the_markers(content: list[str]) -> None:
    assert extract_timeline_section(_paragraphs(*content)) == "Timeline content"


@pytest.mark.parametrize(
    "content",
    [
        ["Some text", "Other text"],
        ["Some text", "Timeline content", END, "Other text"],
        ["Some text", START, "Timeline content", "Other text"],
        [],
    ],
)
def test_extract_is_none_without_both_markers(content: list[str]) -> None:
    assert extract_timeline_section(_paragraphs(*content)) is None


def test_extract_renders_a_linked_run_as_markdown_keeping_its_whitespace() -> None:
    linked = {
        "paragraph": {"elements": [{"textRun": {"content": " link ", "textStyle": {"link": {"url": "http://example.com"}}}}]}
    }

    assert extract_timeline_section(_paragraphs(START, "Timeline content with a", linked, END)) == (
        "Timeline content with a [link](http://example.com) "
    )


@pytest.mark.parametrize(
    "unsupported",
    [
        {"table": {}},
        {"paragraph": {"elements": [{"inlineObjectElement": {}}]}},
    ],
)
def test_extract_refuses_a_section_holding_content_it_cannot_write_back(unsupported: dict[str, Any]) -> None:
    """A table or an image in the section would be lost by a text rewrite, so nothing is returned to rewrite."""
    assert extract_timeline_section(_paragraphs(START, "entry\n", unsupported, END)) is None


def test_find_heading_indices_without_markers_is_none_none() -> None:
    assert find_heading_indices(_indexed("Some text\n"), START, END) == (None, None)


def test_find_heading_indices_with_only_the_start_marker_gives_its_end() -> None:
    start_line = f"{START}\n"
    assert find_heading_indices(_indexed(start_line), START, END) == (1 + len(start_line), None)


def test_find_heading_indices_gives_the_span_between_the_markers() -> None:
    start_line = f"{START}\n"
    assert find_heading_indices(_indexed(start_line, "Some text\n", f"{END}\n"), START, END) == (
        1 + len(start_line),
        1 + len(start_line) + len("Some text\n"),
    )


@pytest.mark.parametrize(
    "content",
    [
        _indexed("Some old content\n", f"{END}\n"),
        _indexed(f"{START}\n", "Some old content\n"),
        _indexed("Some old content\n"),
    ],
)
def test_build_replacement_is_none_without_both_markers(content: list[dict[str, Any]]) -> None:
    assert build_timeline_replacement(content, "new content", START, END) is None


def test_build_replacement_deletes_the_old_section_and_inserts_the_new_text_unlinked() -> None:
    content = _indexed(f"{START}\n", "Some old content\n", f"{END}\n")
    start = 1 + len(f"{START}\n")

    requests = build_timeline_replacement(content, "Unmatched entry content ➡️ Another unmatched entry", START, END)

    assert requests is not None
    assert requests[0] == {"deleteContentRange": {"range": {"startIndex": start, "endIndex": start + len("Some old content\n")}}}
    assert requests[1] == {
        "insertText": {"location": {"index": start}, "text": "\nUnmatched entry content ➡️ Another unmatched entry\n"}
    }
    assert not [request for request in requests[2:] if request.get("updateTextStyle", {}).get("textStyle")]


def test_build_replacement_on_an_empty_section_inserts_without_deleting() -> None:
    content = _indexed(f"{START}\n", f"{END}\n")

    requests = build_timeline_replacement(content, "first", START, END)

    assert requests is not None
    assert not any("deleteContentRange" in request for request in requests)


def test_build_replacement_links_each_markdown_link_at_its_utf16_index() -> None:
    """Text before a link holding a non-BMP character shifts the link by two units per character, as Docs counts."""
    content = _indexed(f"{START}\n", f"{END}\n")
    start = 1 + len(f"{START}\n")
    new_content = "😀 [first](https://example.com/1) then [second](https://example.com/2)"

    requests = build_timeline_replacement(content, new_content, START, END)

    assert requests is not None
    links = [request["updateTextStyle"] for request in requests if request.get("updateTextStyle", {}).get("textStyle")]
    first_at = start + len("\n") + 2 + len(" ")
    second_at = first_at + len("first then ")
    assert links == [
        {
            "range": {"startIndex": first_at, "endIndex": first_at + 5},
            "textStyle": {"link": {"url": "https://example.com/1"}},
            "fields": "link",
        },
        {
            "range": {"startIndex": second_at, "endIndex": second_at + 6},
            "textStyle": {"link": {"url": "https://example.com/2"}},
            "fields": "link",
        },
    ]
    inserted = next(request["insertText"]["text"] for request in requests if "insertText" in request)
    assert inserted == "\n😀 first then second\n"


@pytest.mark.parametrize(
    "url",
    [
        PERMALINK.format("1759435320000100"),
        PERMALINK.format("1759435320000100") + "?thread_ts=1759435000.000001&cid=C123",
        PERMALINK.format("1759435320000100") + "/",
    ],
)
def test_an_entry_is_identified_by_channel_and_full_ts_whatever_the_query(url: str) -> None:
    assert timeline_message_key(url) == ("C123", "1759435320000100")


def test_a_link_that_is_not_a_permalink_is_its_own_identity() -> None:
    assert timeline_message_key("https://example.com/link1") == ("", "https://example.com/link1")


def test_rearrange_sorts_entries_by_their_time_ascending() -> None:
    text = (
        "    ➡️ [2024-03-07 21:53:26 ET](https://example.com/link1) John Doe: Message one\n"
        "    ➡️ [2024-03-05 18:24:30 ET](https://example.com/link2) Jane Smith: Message two\n"
    )

    result = rearrange_by_datetime_ascending(text)

    assert result.index("Message two") < result.index("Message one")


def test_rearrange_keeps_text_before_the_first_entry_and_invalid_lines() -> None:
    text = "Manual note\n➡️ Invalid Entry\n➡️ [2024-03-07 10:00:00 ET](https://example.com/link2) Jane Smith: Message two\n"

    result = rearrange_by_datetime_ascending(text)

    assert result.startswith("Manual note\n➡️ Invalid Entry\n")
    assert "Message two" in result


@pytest.mark.parametrize("text", ["", "Message without datetime\nAnother message"])
def test_rearrange_leaves_text_without_entries_unchanged(text: str) -> None:
    assert rearrange_by_datetime_ascending(text) == text


def test_rearrange_sorts_by_the_message_instant_across_the_dst_fallback() -> None:
    """Both messages show 01:xx ET on the fall-back night; the Slack ts orders them."""
    earlier = f"{int(datetime.fromisoformat('2026-11-01T05:59:00+00:00').timestamp())}.000100"
    later = f"{int(datetime.fromisoformat('2026-11-01T06:01:00+00:00').timestamp())}.000100"
    text = _entry(later, "later", "2026-11-01 01:01:00") + _entry(earlier, "earlier", "2026-11-01 01:59:00")

    result = rearrange_by_datetime_ascending(text)

    assert result.index("earlier") < result.index("later")


def test_with_entry_appends_and_sorts_chronologically() -> None:
    timeline = _entry("1759435380.000200", "second")

    result = timeline_with_entry(timeline, PERMALINK.format("1759435320000100"), _entry("1759435320.000100", "first"))

    assert result is not None
    assert result.index("first") < result.index("second")


def test_with_entry_already_present_is_no_change() -> None:
    timeline = _entry("1759435320.000100", "first")

    assert (
        timeline_with_entry(timeline, PERMALINK.format("1759435320000100") + "?cid=C123", _entry("1759435320.000100", "again"))
        is None
    )


def test_with_entry_keeps_distinct_messages_of_the_same_second() -> None:
    timeline = _entry("1759435320.000200", "second")

    result = timeline_with_entry(timeline, PERMALINK.format("1759435320000100"), _entry("1759435320.000100", "first"))

    assert result is not None
    assert result.count("first") == 1 and result.count("second") == 1
    assert result.index("first") < result.index("second")


def test_with_entry_collapses_copies_left_by_earlier_stale_writes() -> None:
    timeline = _entry("1759435320.000100", "first") * 3

    result = timeline_with_entry(timeline, PERMALINK.format("1759435380000200"), _entry("1759435380.000200", "second"))

    assert result is not None
    assert result.count("first") == 1 and result.count("second") == 1


def test_without_entry_removes_every_copy_and_leaves_others() -> None:
    timeline = _entry("1759435320.000100", "first") + _entry("1759435380.000200", "second") * 2

    result = timeline_without_entry(timeline, PERMALINK.format("1759435380000200"))

    assert result is not None
    assert "second" not in result and result.count("first") == 1


def test_without_entry_absent_is_no_change() -> None:
    assert timeline_without_entry(_entry("1759435320.000100", "first"), PERMALINK.format("1759435380000200")) is None
