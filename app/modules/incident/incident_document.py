"""Module to manage the incident document used to track the details."""

from integrations.google_workspace import google_docs


def update_incident_document_status(document_id, new_status="Closed"):
    """Update the status of the incident document.

    Args:
        document_id (str): The ID of the document to update.
        new_status (str, optional): The new status to set. Defaults to "Closed".

    Returns:
        bool: True if the status was updated, False otherwise.
    """
    # List of possible statuses to be replaced
    possible_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]

    if new_status not in possible_statuses:
        raise ValueError(f"Invalid status: {new_status}")

    # Replace all possible statuses with the new status
    changes = [
        {
            "replaceAllText": {
                "containsText": {"text": f"Status: {status}", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        }
        for status in possible_statuses
        if status != new_status
    ]
    replies = google_docs.batch_update(document_id, changes)["replies"]
    return any(
        reply.get("replaceAllText", {}).get("occurrencesChanged", 0) > 0
        for reply in replies
    )
