from types import SimpleNamespace
from unittest.mock import patch

from modules.incident import incident_document


@patch.object(incident_document, "get_incident_core_settings", new=lambda: SimpleNamespace(report_template_id="test_template_id"))
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
