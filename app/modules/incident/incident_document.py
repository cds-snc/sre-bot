"""Module to manage the incident document used to track the details."""

import datetime

from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters import google_docs as incident_drive
from features.incident.core.adapters.google_docs import replace_placeholders

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
