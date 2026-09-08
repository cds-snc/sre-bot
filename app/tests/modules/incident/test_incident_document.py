from unittest.mock import patch

import pytest

from modules.incident import incident_document

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


def create_mock_document(content):
    def create_paragraph_element(text):
        if isinstance(text, dict):
            return text
        return {"paragraph": {"elements": [{"textRun": {"content": text}}]}}

    return [create_paragraph_element(text) for text in content]


@patch("modules.incident.incident_document.INCIDENT_TEMPLATE", "test_template_id")
@patch("modules.incident.incident_document.incident_drive")
def test_create_incident_document_calls_create_file_from_template(mock_incident_drive):
    title = "Incident 123"
    folder = "test_folder_id"
    mock_incident_drive.create_document_from_template.return_value = {
        "id": "test_document_id",
        "name": title,
    }

    response = incident_document.create_incident_document(title, folder)
    assert response == "test_document_id"

    mock_incident_drive.create_document_from_template.assert_called_once_with(title, folder, "test_template_id")


@patch("modules.incident.incident_document.datetime")
@patch("modules.incident.incident_document.replace_placeholders")
def test_update_boilerplate_text_calls_batch_update(mock_replace_placeholders, mock_datetime):
    document_id = "test_document_id"
    name = "John Doe"
    product = "Product Test"
    slack_channel = "#general"
    on_call_names = "Alice, Bob"

    mock_datetime.datetime.now.return_value.strftime.return_value = "2023-10-01"

    incident_document.update_boilerplate_text(document_id, name, product, slack_channel, on_call_names)

    expected_replacements = {
        "{{date}}": mock_datetime.datetime.now().strftime("%Y-%m-%d"),
        "{{name}}": "John Doe",
        "{{on-call-names}}": "Alice, Bob",
        "{{team}}": "Product Test",
        "{{slack-channel}}": "#general",
        "{{status}}": "In Progress",
    }

    mock_replace_placeholders.assert_called_once_with(document_id, expected_replacements, match_case=True)


@patch("modules.incident.incident_document.replace_placeholders")
def test_update_incident_document_status_changes_occurred(mock_replace_placeholders):
    document_id = "test_document_id"
    new_status = "In Progress"
    mock_replace_placeholders.return_value = True

    response = incident_document.update_incident_document_status(document_id, new_status)
    assert response is True

    expected_replacements = {
        "Status: Open": f"Status: {new_status}",
        "Status: Ready to be Reviewed": f"Status: {new_status}",
        "Status: Reviewed": f"Status: {new_status}",
        "Status: Closed": f"Status: {new_status}",
    }

    mock_replace_placeholders.assert_called_once_with(document_id, expected_replacements, match_case=False)


@patch("modules.incident.incident_document.replace_placeholders")
def test_update_incident_document_status_no_changes_occurred(mock_replace_placeholders):
    document_id = "test_document_id"
    new_status = "In Progress"
    mock_replace_placeholders.return_value = False

    response = incident_document.update_incident_document_status(document_id, new_status)
    assert response is False


def test_update_incident_document_status_invalid_status():
    document_id = "test_document_id"
    invalid_status = "Invalid Status"

    with pytest.raises(ValueError, match=f"Invalid status: {invalid_status}"):
        incident_document.update_incident_document_status(document_id, invalid_status)


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_extract_timeline_content(mock_fetch_document_content):
    content = [START_HEADING, "Timeline content", END_HEADING]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_extract_timeline_content_with_text_before_heading(mock_fetch_document_content):
    content = ["Some text", START_HEADING, "Timeline content", END_HEADING]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_extract_timeline_content_with_text_after_heading(mock_fetch_document_content):
    content = [START_HEADING, "Timeline content", END_HEADING, "Some text"]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_extract_timeline_content_with_text_between_heading(mock_fetch_document_content):
    content = [
        "Start of some text",
        START_HEADING,
        "Timeline content",
        END_HEADING,
        "End of some text",
    ]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_get_timeline_section_no_headings(mock_fetch_document_content):
    content = ["Some text", "Other text"]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_get_timeline_section_missing_start_heading(mock_fetch_document_content):
    content = ["Some text", "Timeline content", END_HEADING, "Other text"]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_get_timeline_section_missing_end_heading(mock_fetch_document_content):
    content = ["Some text", START_HEADING, "Timeline content", "Other text"]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_get_timeline_section_empty_document(mock_fetch_document_content):
    mock_fetch_document_content.return_value = create_mock_document([])

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.fetch_document_content")
def test_get_timeline_section_returns_none_on_classified_fetch_failure(mock_fetch_document_content):
    """AC#6: a classified Docs failure degrades to None instead of crashing."""
    mock_fetch_document_content.return_value = None

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.fetch_document_content")
def test_extract_timeline_content_with_link(mock_fetch_document_content):
    content = [
        START_HEADING,
        "Timeline content with a ",
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "link",
                            "textStyle": {"link": {"url": "http://example.com"}},
                        }
                    }
                ]
            }
        },
        END_HEADING,
    ]
    mock_fetch_document_content.return_value = create_mock_document(content)

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content with a [link](http://example.com)"


def test_no_headings_present_find_heading_indices():
    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 1,
                        "endIndex": 10,
                        "textRun": {"content": "Some text"},
                    }
                ]
            }
        }
    ]
    assert incident_document.find_heading_indices(content, START_HEADING, END_HEADING) == (
        None,
        None,
    )


def test_only_start_heading_present_find_heading_indices():
    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 1,
                        "endIndex": 13,
                        "textRun": {"content": START_HEADING},
                    }
                ]
            }
        }
    ]
    assert incident_document.find_heading_indices(content, START_HEADING, END_HEADING) == (
        13,
        None,
    )


def test_both_headings_present_find_heading_indices():
    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 1,
                        "endIndex": 14,
                        "textRun": {"content": START_HEADING, "endIndex": 13},
                    }
                ]
            }
        },
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 17,
                        "endIndex": 24,
                        "textRun": {"content": "Some text", "endIndex": 22},
                    }
                ]
            }
        },
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 25,
                        "endIndex": 34,
                        "textRun": {
                            "content": END_HEADING,
                            "startIndex": 23,
                            "endIndex": 33,
                        },
                    }
                ]
            }
        },
    ]
    assert incident_document.find_heading_indices(content, START_HEADING, END_HEADING) == (
        14,
        25,
    )


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings(mock_fetch_document_content, mock_apply_document_edits):
    doc_id = "mock_doc_id"
    content = [
        {"paragraph": {"elements": [{"endIndex": 20, "textRun": {"content": START_HEADING}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "startIndex": 20,
                        "endIndex": 40,
                        "textRun": {
                            "content": "Some old content",
                        },
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"startIndex": 40, "textRun": {"content": END_HEADING}}]}},
    ]
    mock_fetch_document_content.return_value = content
    mock_apply_document_edits.return_value = {}

    incident_document.replace_text_between_headings(doc_id, "new content", START_HEADING, END_HEADING)

    assert mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.find_heading_indices")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_more_text(
    mock_fetch_document_content, mock_find_heading_indices, mock_apply_document_edits
):
    doc_id = "mock_doc_id"
    new_content = "[2023-10-01 12:00 ET](http://example.com) John Doe: New content ➡️ [2023-10-01 13:00 ET](http://example.com) Jane Doe: More new content"

    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Blah blah",
                            "endIndex": 40,
                            "startIndex": 1,
                        }
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"textRun": {"content": START_HEADING, "endIndex": 45}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 60,
                            "startIndex": 50,
                        }
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"textRun": {"content": END_HEADING, "startIndex": 70}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 100,
                            "startIndex": 80,
                        }
                    }
                ]
            }
        },
    ]
    mock_fetch_document_content.return_value = content
    mock_find_heading_indices.return_value = (45, 70)
    mock_apply_document_edits.return_value = {}

    incident_document.replace_text_between_headings(doc_id, new_content, START_HEADING, END_HEADING)

    assert mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_start_heading_not_found(mock_fetch_document_content, mock_apply_document_edits):
    doc_id = "mock_doc_id"

    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 40,
                            "startIndex": 20,
                        }
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"textRun": {"content": END_HEADING, "startIndex": 40}}]}},
    ]
    mock_fetch_document_content.return_value = content

    incident_document.replace_text_between_headings(doc_id, "new content", START_HEADING, END_HEADING)

    assert not mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_end_heading_not_found(mock_fetch_document_content, mock_apply_document_edits):
    doc_id = "mock_doc_id"

    content = [
        {"paragraph": {"elements": [{"textRun": {"content": START_HEADING, "endIndex": 20}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 40,
                            "startIndex": 20,
                        }
                    }
                ]
            }
        },
    ]
    mock_fetch_document_content.return_value = content

    incident_document.replace_text_between_headings(doc_id, "new content", START_HEADING, END_HEADING)

    assert not mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_neither_heading_not_found(mock_fetch_document_content, mock_apply_document_edits):
    doc_id = "mock_doc_id"

    content = [
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 40,
                            "startIndex": 20,
                        }
                    }
                ]
            }
        },
    ]
    mock_fetch_document_content.return_value = content

    incident_document.replace_text_between_headings(doc_id, "new content", START_HEADING, END_HEADING)

    assert not mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_content_not_found(mock_fetch_document_content, mock_apply_document_edits):
    """AC#6: a classified Docs failure degrades to a no-op instead of crashing."""
    doc_id = "mock_doc_id"
    mock_fetch_document_content.return_value = None

    incident_document.replace_text_between_headings(doc_id, "new content", START_HEADING, END_HEADING)

    assert not mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.find_heading_indices")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_with_indices(
    mock_fetch_document_content, mock_find_heading_indices, mock_apply_document_edits
):
    doc_id = "mock_doc_id"
    new_content = "[2023-10-01 12:00 ET](http://example.com) John Doe: New content ➡️ [2023-10-01 13:00 ET](http://example.com) Jane Doe: More new content"

    content = [
        {"paragraph": {"elements": [{"textRun": {"content": START_HEADING, "endIndex": 20}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 40,
                            "startIndex": 20,
                        }
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"textRun": {"content": END_HEADING, "startIndex": 40}}]}},
    ]
    mock_fetch_document_content.return_value = content
    mock_find_heading_indices.return_value = (20, 40)
    mock_apply_document_edits.return_value = {}

    incident_document.replace_text_between_headings(doc_id, new_content, START_HEADING, END_HEADING)

    assert mock_apply_document_edits.called


@patch("modules.incident.incident_document.apply_document_edits")
@patch("modules.incident.incident_document.find_heading_indices")
@patch("modules.incident.incident_document.fetch_document_content")
def test_replace_text_between_headings_with_unmatched_entry(
    mock_fetch_document_content, mock_find_heading_indices, mock_apply_document_edits
):
    doc_id = "mock_doc_id"
    new_content = "Unmatched entry content ➡️ Another unmatched entry"

    content = [
        {"paragraph": {"elements": [{"textRun": {"content": START_HEADING, "endIndex": 20}}]}},
        {
            "paragraph": {
                "elements": [
                    {
                        "textRun": {
                            "content": "Some old content",
                            "endIndex": 40,
                            "startIndex": 20,
                        }
                    }
                ]
            }
        },
        {"paragraph": {"elements": [{"textRun": {"content": END_HEADING, "startIndex": 40}}]}},
    ]
    mock_fetch_document_content.return_value = content
    mock_find_heading_indices.return_value = (20, 40)
    mock_apply_document_edits.return_value = {}

    incident_document.replace_text_between_headings(doc_id, new_content, START_HEADING, END_HEADING)

    assert mock_apply_document_edits.called
    # Verify that the unmatched entry was inserted as is
    requests = mock_apply_document_edits.call_args[0][1]
    assert any("Unmatched entry content" in req["insertText"]["text"] for req in requests if "insertText" in req)
    assert any("Another unmatched entry" in req["insertText"]["text"] for req in requests if "insertText" in req)
