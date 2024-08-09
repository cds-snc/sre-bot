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

    content = [create_paragraph_element(text) for text in content]
    return {"body": {"content": content}}


@patch("modules.incident.incident_document.INCIDENT_TEMPLATE", "test_template_id")
@patch("modules.incident.incident_document.google_drive")
def test_create_incident_document_calls_create_file_from_template(mock_google_drive):
    title = "Incident 123"
    folder = "test_folder_id"
    mock_google_drive.create_file_from_template.return_value = {
        "id": "test_document_id",
        "name": title,
    }

    response = incident_document.create_incident_document(title, folder)
    assert response == "test_document_id"

    mock_google_drive.create_file_from_template.assert_called_once_with(
        title, folder, "test_template_id"
    )


@patch("modules.incident.incident_document.datetime")
@patch("modules.incident.incident_document.google_docs")
def test_update_boilerplate_text_calls_batch_update(mock_google_docs, mock_datetime):
    document_id = "test_document_id"
    name = "John Doe"
    product = "Product Test"
    slack_channel = "#general"
    on_call_names = "Alice, Bob"

    mock_datetime.datetime.now.return_value.strftime.return_value = "2023-10-01"
    mock_google_docs.update_boilerplate_text(document_id, name, product, slack_channel, on_call_names)

    expected_requests = [
        {
            "replaceAllText": {
                "containsText": {"text": "{{date}}", "matchCase": "true"},
                "replaceText": mock_datetime.datetime.now().strftime("%Y-%m-%d"),
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{name}}", "matchCase": "true"},
                "replaceText": "John Doe",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{on-call-names}}", "matchCase": "true"},
                "replaceText": "Alice, Bob",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{team}}", "matchCase": "true"},
                "replaceText": "Product Test",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{slack-channel}}", "matchCase": "true"},
                "replaceText": "#general",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "{{status}}", "matchCase": "true"},
                "replaceText": "In Progress",
            }
        },
    ]

    incident_document.update_boilerplate_text(document_id, name, product, slack_channel, on_call_names)
    mock_google_docs.batch_update.assert_called_once_with(document_id, expected_requests)


@patch("modules.incident.incident_document.google_docs")
def test_update_incident_document_status_changes_occurred(google_docs_mock):
    document_id = "test_document_id"
    new_status = "In Progress"
    google_docs_mock.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {"occurrencesChanged": 1}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
        ]
    }

    response = incident_document.update_incident_document_status(
        document_id, new_status
    )
    assert response is True

    expected_changes = [
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Open", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "Status: Ready to be Reviewed",
                    "matchCase": "false",
                },
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Reviewed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Closed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
    ]

    google_docs_mock.batch_update.assert_called_once_with(document_id, expected_changes)


@patch("modules.incident.incident_document.google_docs")
def test_update_incident_document_status_no_changes_occurred(google_docs_mock):
    document_id = "test_document_id"
    new_status = "In Progress"
    google_docs_mock.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
        ]
    }

    response = incident_document.update_incident_document_status(
        document_id, new_status
    )
    assert response is False

    expected_changes = [
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Open", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "Status: Ready to be Reviewed",
                    "matchCase": "false",
                },
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Reviewed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Closed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
    ]

    google_docs_mock.batch_update.assert_called_once_with(document_id, expected_changes)


def test_update_incident_document_status_invalid_status():
    document_id = "test_document_id"
    invalid_status = "Invalid Status"

    with pytest.raises(ValueError, match=f"Invalid status: {invalid_status}"):
        incident_document.update_incident_document_status(document_id, invalid_status)


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_extract_timeline_content(google_docs_mock):
    # Mock document content
    content = [START_HEADING, "Timeline content", END_HEADING]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_extract_timeline_content_with_text_before_heading(google_docs_mock):
    # Mock document content
    content = ["Some text", START_HEADING, "Timeline content", END_HEADING]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_extract_timeline_content_with_text_after_heading(google_docs_mock):
    # Mock document content
    content = [START_HEADING, "Timeline content", END_HEADING, "Some text"]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_extract_timeline_content_with_text_between_heading(google_docs_mock):
    # Mock document content
    content = [
        "Start of some text",
        START_HEADING,
        "Timeline content",
        END_HEADING,
        "End of some text",
    ]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_get_timeline_section_no_headings(google_docs_mock):
    content = ["Some text", "Other text"]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_get_timeline_section_missing_start_heading(google_docs_mock):
    content = ["Some text", "Timeline content", END_HEADING, "Other text"]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_get_timeline_section_missing_end_heading(google_docs_mock):
    content = ["Some text", START_HEADING, "Timeline content", "Other text"]
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_get_timeline_section_empty_document(google_docs_mock):
    mock_document = create_mock_document([])
    google_docs_mock.get_document.return_value = mock_document

    result = incident_document.get_timeline_section("document_id")
    assert result is None


@patch("modules.incident.incident_document.END_HEADING", END_HEADING)
@patch("modules.incident.incident_document.START_HEADING", START_HEADING)
@patch("modules.incident.incident_document.google_docs")
def test_extract_timeline_content_with_link(google_docs_mock):
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
    mock_document = create_mock_document(content)
    google_docs_mock.get_document.return_value = mock_document

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
    assert incident_document.find_heading_indices(
        content, START_HEADING, END_HEADING
    ) == (
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
    assert incident_document.find_heading_indices(
        content, START_HEADING, END_HEADING
    ) == (
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
    assert incident_document.find_heading_indices(
        content, START_HEADING, END_HEADING
    ) == (
        14,
        25,
    )


@patch("modules.incident.incident_document.google_docs")
def test_replace_text_between_headings(mock_google_docs):
    doc_id = ""
    # Mock document content
    mock_document = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": START_HEADING, "endIndex": 20}}
                        ]
                    }
                },
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
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": END_HEADING, "startIndex": 40}}
                        ]
                    }
                },
            ]
        }
    }
    mock_google_docs.get_document.return_value.documents().get().execute.return_value = (
        mock_document
    )
    mock_google_docs.get_document.return_value.documents().batchUpdate().execute.return_value = (
        {}
    )

    incident_document.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )
    assert mock_google_docs.get_document.return_value.documents().batchUpdate.called


@patch("modules.incident.incident_document.find_heading_indices")
@patch("modules.incident.incident_document.google_docs")
def test_replace_text_between_headings_more_text(
    mock_google_docs, mock_find_heading_indices
):
    doc_id = "mock_doc_id"
    new_content = "[2023-10-01 12:00 ET](http://example.com) John Doe: New content ➡️ [2023-10-01 13:00 ET](http://example.com) Jane Doe: More new content"

    # Mock document content
    mock_document = {
        "body": {
            "content": [
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
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": START_HEADING, "endIndex": 45}}
                        ]
                    }
                },
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
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": END_HEADING, "startIndex": 70}}
                        ]
                    }
                },
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
        }
    }
    mock_google_docs.get_document.return_value = mock_document
    mock_find_heading_indices.return_value = (45, 70)
    mock_google_docs.batch_update.return_value = {
        "replaceAllText": {"occurrencesChanged": 5}
    }

    incident_document.replace_text_between_headings(
        doc_id, new_content, START_HEADING, END_HEADING
    )


@patch("modules.incident.incident_document.google_docs")
def test_replace_text_between_headings_start_heading_not_found(mock_google_docs):
    doc_id = "mock_doc_id"

    # Mock document content where start heading does not exist
    mock_document = {
        "body": {
            "content": [
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
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": END_HEADING, "startIndex": 40}}
                        ]
                    }
                },
            ]
        }
    }
    mock_google_docs.get_document.return_value.return_value = mock_document
    # mock_google_docs.get_document.return_value.documents().get().execute.return_value = (
    #     mock_document
    # )

    incident_document.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_google_docs.batch_update.called


@patch("modules.incident.incident_document.google_docs")
def test_replace_text_between_headings_end_heading_not_found(mock_google_docs):
    doc_id = "mock_doc_id"

    # Mock document content where start heading does not exist
    mock_document = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": START_HEADING, "endIndex": 20}}
                        ]
                    }
                },
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
        }
    }
    mock_google_docs.get_document.return_value = mock_document

    incident_document.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_google_docs.batch_update.called


@patch("modules.incident.incident_document.google_docs")
def test_replace_text_between_headings_neither_heading_not_found(mock_google_docs):
    doc_id = "mock_doc_id"

    # Mock document content where start heading does not exist
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

    mock_document = create_mock_document(content)

    mock_google_docs.get_document.return_value.documents().get().execute.return_value = (
        mock_document
    )

    incident_document.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_google_docs.get_document.return_value.documents().batchUpdate.called


@patch("modules.incident.incident_document.google_docs")
@patch("modules.incident.incident_document.find_heading_indices")
def test_replace_text_between_headings_with_indices(
    mock_find_heading_indices, mock_google_docs
):
    doc_id = "mock_doc_id"
    new_content = "[2023-10-01 12:00 ET](http://example.com) John Doe: New content ➡️ [2023-10-01 13:00 ET](http://example.com) Jane Doe: More new content"

    # Mock document content
    content = [
        {
            "paragraph": {
                "elements": [{"textRun": {"content": START_HEADING, "endIndex": 20}}]
            }
        },
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
        {
            "paragraph": {
                "elements": [{"textRun": {"content": END_HEADING, "startIndex": 40}}]
            }
        },
    ]

    mock_document = create_mock_document(content)
    mock_google_docs.get_document.return_value = mock_document
    mock_find_heading_indices.return_value = (20, 40)

    mock_google_docs.batch_update.return_value = {}

    incident_document.replace_text_between_headings(
        doc_id, new_content, START_HEADING, END_HEADING
    )

    assert mock_google_docs.batch_update.called


@patch("modules.incident.incident_document.google_docs")
@patch("modules.incident.incident_document.find_heading_indices")
def test_replace_text_between_headings_with_unmatched_entry(
    mock_find_heading_indices, mock_google_docs
):
    doc_id = "mock_doc_id"
    new_content = "Unmatched entry content ➡️ Another unmatched entry"

    # Mock document content
    content = [
        {
            "paragraph": {
                "elements": [{"textRun": {"content": START_HEADING, "endIndex": 20}}]
            }
        },
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
        {
            "paragraph": {
                "elements": [{"textRun": {"content": END_HEADING, "startIndex": 40}}]
            }
        },
    ]

    mock_document = {"body": {"content": content}}
    mock_google_docs.get_document.return_value = mock_document
    mock_find_heading_indices.return_value = (20, 40)

    mock_google_docs.batch_update.return_value = {}

    incident_document.replace_text_between_headings(
        doc_id, new_content, START_HEADING, END_HEADING
    )

    assert mock_google_docs.batch_update.called
    # Verify that the unmatched entry was inserted as is
    requests = mock_google_docs.batch_update.call_args[0][1]
    assert any(
        "Unmatched entry content" in req["insertText"]["text"]
        for req in requests
        if "insertText" in req
    )
    assert any(
        "Another unmatched entry" in req["insertText"]["text"]
        for req in requests
        if "insertText" in req
    )
