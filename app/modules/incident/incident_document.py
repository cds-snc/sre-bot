"""Module to manage the incident document used to track the details."""

import datetime

from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters import google_docs as incident_drive
from features.incident.core.adapters.google_docs import replace_placeholders, status_line_replacements

# The timeline rewrite lives in features.incident.core.adapters.google_docs (decisions/migration.md rule 5).


def create_incident_document(title, folder):
    """Create a new incident document in Google Docs.

    Args:
        title (str): The title of the new document.

    Returns:
        str: The ID of the new document.
    """
    document_id = ""
    response = incident_drive.create_document_from_template(title, folder, get_incident_core_settings().report_template_id)
    if response:
        document_id = str(response.get("id") or "")

    return document_id


def update_boilerplate_text(document_id, name, product, slack_channel, on_call_names):
    replacements = {
        "{{date}}": datetime.datetime.now().strftime("%Y-%m-%d"),
        "{{name}}": str(name),
        "{{on-call-names}}": str(on_call_names),
        "{{team}}": str(product),
        "{{slack-channel}}": str(slack_channel),
        "{{status}}": "In Progress",
    }

    replace_placeholders(document_id, replacements, match_case=True)


def update_incident_document_status(document_id, new_status="Closed"):
    """Update the status of the incident document.

    Args:
        document_id (str): The ID of the document to update.
        new_status (str, optional): The new status to set. Defaults to "Closed".

    Returns:
        bool: True if the status was updated, False otherwise.
    """
    if new_status not in set(IncidentStatus):
        raise ValueError(f"Invalid status: {new_status}")

    # The mapping lives in core (decisions/migration.md rule 5); TASK-145.8.3 deletes this function with its last caller (information_update.py).
    return replace_placeholders(document_id, status_line_replacements(IncidentStatus(new_status)), match_case=False)
