"""Module to manage the incident document used to track the details."""

import logging
import re
from integrations.google_workspace import google_docs

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


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


def get_timeline_section(document_id):
    # Retrieve the document
    document = google_docs.get_document(document_id)
    content = document.get("body").get("content")

    timeline_content = ""
    record = False
    found_start = False
    found_end = False

    # Iterate through the elements of the document
    for element in content:
        if "paragraph" in element:
            paragraph_elements = element.get("paragraph").get("elements")
            for elem in paragraph_elements:
                text_run = elem.get("textRun")
                if text_run:
                    text = text_run.get("content")
                    textStyle = text_run.get("textStyle", {})
                    if "link" in textStyle:
                        # Extract link URL
                        link = textStyle["link"].get("url")
                        # Format the text with the link as Markdown
                        formatted_text = f"[{text.strip()}]({link})"
                        # Replace the text with the formatted text
                        text = formatted_text
                    if START_HEADING in text:
                        record = True
                        found_start = True
                    elif END_HEADING in text:
                        found_end = True
                        if found_start:
                            return timeline_content
                    elif record:
                        timeline_content += text

    # Return None if either START_HEADING or END_HEADING not found
    return None if not (found_start and found_end) else timeline_content


def find_heading_indices(content, start_heading, end_heading):
    """Find the start and end indices of content between two headings."""
    start_index, end_index = None, None
    for element in content:
        if "paragraph" in element:
            text_runs = element["paragraph"].get("elements", [])
            for text_run in text_runs:
                text = text_run.get("textRun", {}).get("content", "")
                if start_heading in text:
                    start_index = text_run.get("endIndex")
                elif end_heading in text and start_index is not None:
                    end_index = text_run.get("startIndex")
                    return start_index, end_index
    return start_index, end_index


# Replace the text between the headings
def replace_text_between_headings(doc_id, new_content, start_heading, end_heading):

    document = google_docs.get_document(doc_id)
    content = document.get("body").get("content")

    # Find the start and end indices
    start_index, end_index = find_heading_indices(content, start_heading, end_heading)

    if start_index is not None and end_index is not None:
        # Delete the existing content from the document
        requests = [
            {
                "deleteContentRange": {
                    "range": {"startIndex": start_index, "endIndex": end_index}
                }
            }
        ]

        # split the formatted content by the emoji
        line = new_content.split(" ➡ ")
        pattern = r"\[([^\]]+)\]\(([^)]+)\)\s([^:]+):\s(.+)"
        insert_index = start_index
        inserted_content = ""

        # Insert an empty line before the new content and after the placeholder text
        text_to_insert = "\n"
        text_len = len(text_to_insert)
        requests.append(
            {
                "insertText": {
                    "location": {"index": insert_index},
                    "text": text_to_insert,
                }
            }
        )
        # udpate the insert index
        insert_index += text_len

        for item in line:
            # split the item by the emoji and strip out any empty strings
            original_entries = item.split("➡️ ")
            entries = [entry for entry in original_entries if entry.strip()]

            for entry in entries:
                # Regular expression to match the entry pattern
                pattern = r"\[(?P<date>.+?) ET\]\((?P<url>.+?)\) (?P<name>.+?): (?P<message>.+)$"

                # Use re.DOTALL to make '.' match newline characters as well. This is needed for multi-line messages
                match = re.match(pattern, entry, re.DOTALL)

                if match:
                    # Extract components from the match object
                    date = match.group("date") + " ET"
                    url = match.group("url")
                    name = match.group("name")
                    message = match.group(
                        "message"
                    ).strip()  # Remove leading/trailing whitespace

                    # Construct the text to be inserted with the date as a link
                    text_to_insert = f" ➡️ {date} {name}: {message}\n"
                    text_len = len(text_to_insert)
                    inserted_content += text_to_insert

                    # Insert text request
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": insert_index},
                                "text": text_to_insert,
                            }
                        }
                    )
                    # Update link style for date_text
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": insert_index + 4,
                                    "endIndex": insert_index + len(date) + 4,
                                },
                                "textStyle": {"link": {"url": url}},
                                "fields": "link",
                            }
                        }
                    )
                    # Update for next insertion
                    insert_index += text_len
                else:
                    # if we don't match the above pattern, just insert the entry as is
                    text_to_insert = f" ➡️ {item}\n"
                    inserted_content += text_to_insert
                    text_len = len(text_to_insert)
                    # Insert text request for the entire block of formatted_content
                    requests.append(
                        {
                            "insertText": {
                                "location": {"index": insert_index},
                                "text": text_to_insert,
                            }
                        }
                    )

                    # Update insert_index as needed, assuming formatted_content is a single block of text
                    insert_index += text_len

                # Make sure that we do normal formatting for the inserted content
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": start_index,
                                "endIndex": (start_index + len(inserted_content)),
                            },
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "fields": "namedStyleType",
                        }
                    }
                )
        google_docs.batch_update(doc_id, requests)
        # service.documents().batchUpdate(
        #     documentId=doc_id, body={"requests": requests}
        # ).execute()
    else:
        logging.warning("Headings not found")
