import re
from datetime import datetime
import pytz  # type: ignore
from integrations.google_workspace import google_docs
from integrations.slack import users as slack_users
from integrations.google_drive import (
    get_timeline_section,
    replace_text_between_headings,
)

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


def rearrange_by_datetime_ascending(text):
    lines = text.split("\n")
    entries = []

    pattern = r"\s*➡️\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ET\]\((https?://[\w./-]+)\)\s([\w\s]+):\s"

    current_message = []
    for line in lines:
        match = re.match(pattern, line)
        if match:
            if (
                current_message
            ):  # If there's a current message, finalize it before starting a new one
                entries.append(current_message)
                current_message = []
            date_str, url, name = match.groups()
            dt = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
            msg_start = line[match.end() :].strip(" ")
            current_message = [dt, url, f"{name}:", msg_start]
        elif current_message:  # If it's a continuation of the current message
            current_message[-1] += "\n" + f"{line.strip()}"

    if current_message:  # Don't forget to append the last message
        entries.append(current_message)

    # Sort the entries by datetime in ascending order
    sorted_entries = sorted(entries, key=lambda x: x[0])

    # Reformat the entries back into strings, including 'ET' and the full message
    sorted_text = "\n\n".join(
        [
            f"➡️ [{entry[0].strftime('%Y-%m-%d %H:%M:%S')} ET]({entry[1]}) {entry[2]} {entry[3]}"
            for entry in sorted_entries
        ]
    )

    return sorted_text


def convert_epoch_to_datetime_est(epoch_time):
    """
    Convert an epoch time to a standard date/time format in Eastern Standard Time (ET).

    Args:
    epoch_time (float): The epoch time.

    Returns:
    str: The corresponding date and time in the format YYYY-MM-DD HH:MM:SS ET.
    """
    # Define the Eastern Standard Timezone
    est = pytz.timezone("US/Eastern")

    # Convert epoch time to a datetime object in UTC
    utc_datetime = datetime.utcfromtimestamp(float(epoch_time))

    # Convert UTC datetime object to ET
    est_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(est)

    # Format the datetime object to a string in the desired format with 'ET' at the end
    return est_datetime.strftime("%Y-%m-%d %H:%M:%S") + " ET"


def handle_forwarded_messages(message):
    """
    Append forwarded messages from attachments to the original message text.

    This function checks if there are any attachments in the given message. If any
    forwarded messages are found in the attachments, their 'fallback' text is cleaned
    of triple backticks and appended to the message text with a "Forwarded Message:" prefix.

    Parameters:
    - message: A dictionary representing the message. It is expected to have keys
      'text' and optionally 'attachments'. 'attachments' should be a list where each
      item is a dictionary containing a key 'fallback' for the forwarded message text.

    Returns:
    - message: The updated message dictionary with forwarded messages appended to the text.
    """
    # get the forwarded message and get the attachments appeending the forwarded message to the original message
    if message.get("attachments"):
        attachments = message["attachments"]
        for attachment in attachments:
            fallback = attachment.get("fallback")
            if fallback:
                attachment["fallback"] = attachment["fallback"].replace("```", "")
                message["text"] += "\nForwarded Message: " + attachment["fallback"]
    return message


def handle_images_in_message(message):
    """
    Append image URLs to the text in a message.

    This function checks if there are any files in the given message. If any images
    are found, their URLs are appended to the message text.

    Parameters:
    - message: A dictionary representing the message. It is expected to have keys
      'text' and 'files'. 'files' should be a list where each item is a dictionary
      containing a key 'url_private' for the image URL.

    Returns:
    - message: The updated message dictionary with image URLs appended to the text.
    """
    # get the images in the message and append them to the original message
    if "files" in message:
        image = message["files"][0]["url_private"]
        if message["text"] != "":
            message["text"] += "\n"
        message["text"] += f"Image: {image}"
    return message


def get_incident_document_id(client, channel_id, logger):
    """
    Retrieve the incident report document ID from the incident channel.

    This function fetches the list of bookmarks for the specified channel
    and looks for a bookmark titled "Incident report". If found, it extracts
    the Google Docs document ID from the bookmark link.

    Parameters:
    - client: The client instance used to interact with the API.
    - channel_id: The ID of the channel to fetch bookmarks from.
    - logger: The logger instance used for logging error messages.

    Returns:
    - document_id: The ID of the Google Docs incident report document, or an
      empty string if no such document is found.
    """
    document_id = ""
    response = client.bookmarks_list(channel_id=channel_id)
    if response["ok"]:
        for item in range(len(response["bookmarks"])):
            if response["bookmarks"][item]["title"] == "Incident report":
                document_id = google_docs.extract_google_doc_id(
                    response["bookmarks"][item]["link"]
                )
                if document_id == "":
                    logger.error("No incident document found for this channel.")
    return document_id
