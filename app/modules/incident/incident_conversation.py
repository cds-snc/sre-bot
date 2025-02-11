import re
from datetime import datetime
import pytz  # type: ignore
from slack_sdk import WebClient  # type: ignore
from slack_sdk.errors import SlackApiError  # type: ignore
from integrations.google_workspace import google_docs
from integrations.slack import users as slack_users
from integrations.sentinel import log_to_sentinel

from modules.incident.incident_document import (
    get_timeline_section,
    replace_text_between_headings,
)
from modules.incident import incident_helper, schedule_retro

START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


# Make sure that we are listening only on floppy disk reaction
def is_floppy_disk(event: dict) -> bool:
    return event["reaction"] == "floppy_disk"


# We need to ack all other reactions so that they don't get processed
def just_ack_the_rest_of_reaction_events():
    pass


def is_incident_channel(client: WebClient, logger, channel_id: str):
    is_incident = False
    is_dev_incident = False
    try:
        channel_info = client.conversations_info(channel=channel_id)
        if channel_info.get("ok"):
            channel: dict = channel_info.get("channel", {})
            name: str = channel.get("name", "")
            is_member = channel.get("is_member")
            is_archived = channel.get("is_archived")
            is_incident = name.startswith("incident-")
            is_dev_incident = name.startswith("incident-dev-")
            if is_incident and not is_archived and not is_member:
                response = client.conversations_join(channel=channel_id)
                if not response.get("ok"):
                    raise SlackApiError("Error joining the channel", response)
        else:
            raise SlackApiError("Error getting the channel info", channel_info)
    except SlackApiError as e:
        logger.error(f"Error with client request: {e}")
        raise e
    return is_incident, is_dev_incident


def rearrange_by_datetime_ascending(text):
    lines = text.split("\n")
    entries = []

    pattern = r"\s*➡️\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ET\]\((https?://[\w./-]+(?:\?\w+=\d+\.\d+&\w+=\w+)?)\)\s([\w\s]+):\s"

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


def handle_reaction_added(client, ack, body, logger):
    ack()
    # get the channel in which the reaction was used
    channel_id = body["event"]["item"]["channel"]
    # Get the channel name which requires us to use the conversations_info API call
    channel_name = client.conversations_info(channel=channel_id)["channel"]["name"]

    # if the emoji added is a floppy disk emoji and we are in an incident channel, then add the message to the incident timeline
    if channel_name.startswith("incident-"):
        # get the message from the conversation
        try:
            # get the messages from the conversation and incident channel
            messages = return_messages(client, body, channel_id)

            # get the incident report document id from the incident channel
            document_id = get_incident_document_id(client, channel_id, logger)

            for message in messages:
                # get the forwarded message and get the attachments appending the forwarded message to the original message
                message = handle_forwarded_messages(message)

                # get the message ts time
                message_ts = message["ts"]

                # convert the time which is now in epoch time to standard ET Time
                message_date_time = convert_epoch_to_datetime_est(message_ts)

                # get a link to the message
                link = client.chat_getPermalink(
                    channel=channel_id, message_ts=message_ts
                )["permalink"]

                # get the user name from the message
                user = client.users_profile_get(user=message["user"])
                # get the full name of the user so that we include it into the timeline
                user_full_name = user["profile"]["real_name"]

                # get the current timeline section content
                content = get_timeline_section(document_id)

                # handle any images in the messages
                message = handle_images_in_message(message)

                # if the message contains mentions to other slack users, replace those mentions with their name
                message = slack_users.replace_user_id_with_handle(
                    client, message["text"]
                )

                # if the message already exists in the timeline, then don't put it there again
                if content and message_date_time not in content:
                    # append the new message to the content
                    content += (
                        f" ➡️ [{message_date_time}]({link}) {user_full_name}: {message}"
                    )

                    # sort all the message to be in ascending chronological order
                    sorted_content = rearrange_by_datetime_ascending(content)

                    # replace the content in the file with the new headings
                    replace_text_between_headings(
                        document_id, sorted_content, START_HEADING, END_HEADING
                    )
        except Exception as e:
            logger.error(e)


# Execute this function when a reaction was removed
def handle_reaction_removed(client, ack, body, logger):
    ack()
    # get the channel id
    channel_id = body["event"]["item"]["channel"]

    # Get the channel name which requires us to use the conversations_info API call
    result = client.conversations_info(channel=channel_id)
    channel_name = result["channel"]["name"]

    if channel_name.startswith("incident-"):
        try:
            messages = return_messages(client, body, channel_id)

            if not messages:
                logger.warning("No messages found")
                return
            # get the message we want to delete
            message = messages[0]

            # get the forwarded message and get the attachments appeending the forwarded message to the original message
            message = handle_forwarded_messages(message)

            # get the message ts time
            message_ts = message["ts"]

            # convert the epoch time to standard ET day/time
            message_date_time = convert_epoch_to_datetime_est(message_ts)

            # get the user of the person that send the message
            user = client.users_profile_get(user=message["user"])
            # get the user's full name
            user_full_name = user["profile"]["real_name"]

            # get the incident report document id from the incident channel
            document_id = get_incident_document_id(client, channel_id, logger)

            # get the current content from the document
            content = get_timeline_section(document_id)

            # handle any images in the message
            message = handle_images_in_message(message)

            # if the message contains mentions to other slack users, replace those mentions with their name
            message = slack_users.replace_user_id_with_handle(client, message["text"])

            # get a link to the message
            link = client.chat_getPermalink(channel=channel_id, message_ts=message_ts)[
                "permalink"
            ]

            # Construct the message to remove
            message_to_remove = (
                f" ➡️ [{message_date_time}]({link}) {user_full_name}: {message}\n"
            )

            # Remove the message
            if message_to_remove in content:
                content = content.replace(message_to_remove, "\n")

                # Update the timeline content
                result = replace_text_between_headings(
                    document_id,
                    content,
                    START_HEADING,
                    END_HEADING,
                )
            else:
                logger.warning("Message not found in the timeline")
                return
        except Exception as e:
            logger.error(e)


# Function to return the messages from the conversation
def return_messages(client, body, channel_id):
    # Fetch the message that had the reaction added or removed
    result = client.conversations_history(
        channel=channel_id,
        limit=1,
        inclusive=True,
        include_all_metadata=True,
        ts=body["event"]["item"]["ts"],
    )
    # get the messages
    messages = result["messages"]

    # if there are more messages in the conversation, get them
    if result["has_more"]:
        result = client.conversations_replies(
            channel=channel_id,
            ts=body["event"]["item"]["ts"],
            inclusive=True,
            limit=1,
        )
        messages = result["messages"]

        # get the parent massages if there are more threads
        if messages.__len__() > 1:
            return [messages[0]]

    return messages


def archive_channel_action(client: WebClient, logger, body, ack, respond):
    ack()
    channel_id = body["channel"]["id"]
    action = body["actions"][0]["value"]
    channel_name = body["channel"]["name"]
    user = body["user"]["id"]

    # get the current chanel id and name and make up the body with those 2 values
    channel_info = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user_id": user,
    }

    if action == "ignore":
        msg = (
            f"<@{user}> has delayed scheduling and archiving this channel for 14 days."
        )
        client.chat_update(
            channel=channel_id, text=msg, ts=body["message_ts"], attachments=[]
        )
        log_to_sentinel("incident_channel_archive_delayed", body)
    elif action == "archive":
        # Call the close_incident function to update the incident document to closed, update the spreadsheet and archive the channel
        incident_helper.close_incident(client, logger, channel_info, ack, respond)
        # log the event to sentinel
        log_to_sentinel("incident_channel_archived", body)
    elif action == "schedule_retro":
        channel_info["trigger_id"] = body["trigger_id"]
        schedule_retro.schedule_incident_retro(client, channel_info, ack)
        # log the event to sentinel
        log_to_sentinel("incident_retro_scheduled", body)
