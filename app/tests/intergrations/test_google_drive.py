import os
import pytest

from integrations import google_drive

from unittest.mock import patch

# Constants for the test
START_HEADING = "Detailed Timeline"
END_HEADING = "Trigger"


@patch("integrations.google_drive.build")
@patch("integrations.google_drive.pickle")
def test_get_google_service_returns_build_object(pickle_mock, build_mock):
    google_drive.get_google_service("drive", "v3")
    build_mock.assert_called_once_with(
        "drive", "v3", credentials=pickle_mock.loads(os.environ.get("PICKLE_STRING"))
    )


@patch("integrations.google_drive.PICKLE_STRING", False)
def test_get_google_service_raises_exception_if_pickle_string_not_set():
    with pytest.raises(Exception) as e:
        google_drive.get_google_service("drive", "v3")
    assert "Pickle string not set" in str(e.value)


@patch("integrations.google_drive.pickle")
def test_get_google_service_raises_exception_if_pickle_string_is_invalid(pickle_mock):
    pickle_mock.loads.side_effect = Exception("Invalid pickle string")
    with pytest.raises(Exception) as e:
        google_drive.get_google_service("drive", "v3")
    assert "Invalid pickle string" in str(e.value)


@patch("integrations.google_drive.get_google_service")
def test_add_metadata_returns_result(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }
    result = google_drive.add_metadata("file_id", "key", "value")
    assert result == {"name": "test_folder", "appProperties": {"key": "value"}}


@patch("integrations.google_drive.get_google_service")
def test_create_folder_returns_folder_name(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "name": "test_folder"
    }
    assert google_drive.create_folder("test_folder") == "Created folder test_folder"


@patch("integrations.google_drive.get_google_service")
def test_create_new_folder_returns_folder_id(get_google_service_mock):
    # test that a new folder created returns the folder id
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "foo"
    }
    assert google_drive.create_new_folder("name", "parent_folder") == "foo"


@patch("integrations.google_drive.get_google_service")
def test_create_new_incident(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "test_incident"
    }
    assert (
        google_drive.create_new_incident("test_incident", "test_folder")
        == "test_incident"
    )


@patch("integrations.google_drive.get_google_service")
def test_create_new_google_doc_file(get_google_service_mock):
    # test that a new google doc is successfully created
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "google_doc_id"
    }
    assert (
        google_drive.create_new_docs_file("name", "parent_folder_id") == "google_doc_id"
    )


@patch("integrations.google_drive.get_google_service")
def test_update_incident_file(get_google_service_mock):
    # test that incident doc's status is
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "google_doc_id"
    }
    assert (
        google_drive.create_new_docs_file("name", "parent_folder_id") == "google_doc_id"
    )


@patch("integrations.google_drive.get_google_service")
def test_create_new_google_sheets_file(get_google_service_mock):
    # test that a new google sheets is successfully created
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "google_sheets_id"
    }
    assert (
        google_drive.create_new_sheets_file("name", "parent_folder_id")
        == "google_sheets_id"
    )


@patch("integrations.google_drive.get_google_service")
def test_copy_file_to_folder(get_google_service_mock):
    # test that we can successfully copy files to a different folder
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "file_id"
    }
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "id": "updated_file_id"
    }
    assert (
        google_drive.copy_file_to_folder(
            "file_id", "name", "parent_folder", "destination_folder"
        )
        == "updated_file_id"
    )


@patch("integrations.google_drive.get_google_service")
def test_delete_metadata_returns_result(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {},
    }
    result = google_drive.delete_metadata("file_id", "key")
    get_google_service_mock.return_value.files.return_value.update.assert_called_once_with(
        fileId="file_id",
        body={"appProperties": {"key": None}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {}}


@patch("integrations.google_drive.get_google_service")
def test_get_document_by_channel_name(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "name": "test_document",
                "id": "test_document_id",
                "appProperties": {},
            }
        ]
    }
    assert google_drive.get_document_by_channel_name("test_channel_name") == [
        {"name": "test_document", "id": "test_document_id", "appProperties": {}}
    ]


@patch("integrations.google_drive.get_google_service")
def test_list_folders_returns_folder_names(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.list.return_value.execute.return_value = {
        "files": [{"name": "test_folder"}]
    }
    assert google_drive.list_folders() == [{"name": "test_folder"}]


@patch("integrations.google_drive.get_google_service")
def test_list_metadata(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.get.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }

    assert google_drive.list_metadata("file_id") == {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }


@patch("integrations.google_drive.get_google_service")
def test_merge_data(get_google_service_mock):
    get_google_service_mock.return_value.documents.return_value.batchUpdate.return_value.execute.return_value = (
        True
    )
    assert (
        google_drive.merge_data("file_id", "name", "product", "slack_channel", "")
        is True
    )


@patch("integrations.google_drive.get_google_service")
def test_update_incident_list(get_google_service_mock):
    get_google_service_mock.return_value.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = (
        True
    )
    assert (
        google_drive.update_incident_list(
            "document_link", "name", "slug", "product", "channel_url"
        )
        is True
    )


@patch("integrations.google_drive.get_google_service")
def test_close_incident_document(get_google_service_mock):
    # Define a mock response for the batchUpdate call
    get_google_service_mock.return_value.documents.return_value.batchUpdate.return_value.execute.return_value = {
        "status": "success"
    }

    # Assert that the function returns the correct response
    assert google_drive.close_incident_document("file_id") == {"status": "success"}


@patch("integrations.google_drive.get_google_service")
def test_update_spreadsheet(get_google_service_mock):
    # Define a mock response for the get values call
    mock_values = [
        ["Channel A", "Detail 1", "Open"],
        ["Channel B", "Detail 2", "In Progress"],
        ["Channel C", "Detail 3", "Reviewed"],
    ]

    # get the return values from the mock
    get_google_service_mock.return_value.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": mock_values
    }

    # Define a channel name to search for
    channel_name = "Channel B"

    # assert that the function returns the correct response
    assert google_drive.update_spreadsheet_close_incident(channel_name) is True


def create_mock_document(content):
    elements = [
        {
            "paragraph": {
                "elements": [
                    {"startIndex": 1, "endIndex": 200, "textRun": {"content": text}}
                ]
            }
        }
        for text in content
    ]
    return {"body": {"content": elements}}


@patch("integrations.google_drive.get_google_service")
def test_extract_timeline_content(mock_service):
    # Mock document content
    content = [START_HEADING, "Timeline content", END_HEADING]
    mock_document = create_mock_document(content)
    print("Mock document is ", mock_document)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("integrations.google_drive.get_google_service")
def test_extract_timeline_content_with_text_before_heading(mock_service):
    # Mock document content
    content = ["Some text", START_HEADING, "Timeline content", END_HEADING]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("integrations.google_drive.get_google_service")
def test_extract_timeline_content_with_text_after_heading(mock_service):
    # Mock document content
    content = [START_HEADING, "Timeline content", END_HEADING, "Some text"]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("integrations.google_drive.get_google_service")
def test_extract_timeline_content_with_text_between_heading(mock_service):
    # Mock document content
    content = [
        "Start of some text",
        START_HEADING,
        "Timeline content",
        END_HEADING,
        "End of some text",
    ]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result == "Timeline content"


@patch("integrations.google_drive.get_google_service")
def test_get_timeline_section_no_headings(mock_service):
    content = ["Some text", "Other text"]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result is None


@patch("integrations.google_drive.get_google_service")
def test_get_timeline_section_missing_start_heading(mock_service):
    content = ["Some text", "Timeline content", END_HEADING, "Other text"]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result is None


@patch("integrations.google_drive.get_google_service")
def test_get_timeline_section_missing_end_heading(mock_service):
    content = ["Some text", START_HEADING, "Timeline content", "Other text"]
    mock_document = create_mock_document(content)
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result is None


@patch("integrations.google_drive.get_google_service")
def test_get_timeline_section_empty_document(mock_service):
    mock_document = create_mock_document([])
    mock_service.return_value.documents().get().execute.return_value = mock_document

    result = google_drive.get_timeline_section("document_id")
    assert result is None


@patch("integrations.google_drive.get_google_service")
def test_replace_text_between_headings(mock_service):
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
    mock_service.return_value.documents().get().execute.return_value = mock_document
    mock_service.return_value.documents().batchUpdate().execute.return_value = {}

    google_drive.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )
    assert mock_service.return_value.documents().batchUpdate.called


@patch("integrations.google_drive.get_google_service")
def test_replace_text_between_headings_more_text(mock_service):
    doc_id = ""
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
    mock_service.return_value.documents().get().execute.return_value = mock_document
    mock_service.return_value.documents().batchUpdate().execute.return_value = {}

    google_drive.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )
    assert mock_service.return_value.documents().batchUpdate.called


@patch("integrations.google_drive.get_google_service")
def test_replace_text_between_headings_start_heading_not_found(mock_service):
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
    mock_service.return_value.documents().get().execute.return_value = mock_document

    google_drive.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_service.return_value.documents().batchUpdate.called


@patch("integrations.google_drive.get_google_service")
def test_replace_text_between_headings_end_heading_not_found(mock_service):
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
    mock_service.return_value.documents().get().execute.return_value = mock_document

    google_drive.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_service.return_value.documents().batchUpdate.called


@patch("integrations.google_drive.get_google_service")
def test_replace_text_between_headings_neither_heading_not_found(mock_service):
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
            ]
        }
    }
    mock_service.return_value.documents().get().execute.return_value = mock_document

    google_drive.replace_text_between_headings(
        doc_id, mock_document, START_HEADING, END_HEADING
    )

    # Check if batchUpdate was not called as the start heading was not found
    assert not mock_service.return_value.documents().batchUpdate.called


@patch("integrations.google_drive.list_metadata")
def test_healthcheck_healthy(mock_list_metadata):
    mock_list_metadata.return_value = {"id": "test_doc"}
    assert google_drive.healthcheck() is True


@patch("integrations.google_drive.list_metadata")
def test_healthcheck_unhealthy(mock_list_metadata):
    mock_list_metadata.return_value = None
    assert google_drive.healthcheck() is False
