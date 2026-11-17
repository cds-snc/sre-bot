from datetime import datetime
from zoneinfo import ZoneInfo

import i18n  # type: ignore
import pytz  # type: ignore
from slack_sdk import WebClient  # type: ignore
from slack_sdk.errors import SlackApiError  # type: ignore
from slack_sdk.web import SlackResponse  # type: ignore
from structlog import get_logger

from contracts.configuration import host_info
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters import google_docs as incident_documents
from integrations.sentinel import log_to_sentinel
from integrations.slack import users as slack_users
from modules.incident import incident_helper, schedule_retro
from modules.incident.incident_document import (
    TIMELINE_ENTRY_PATTERN,
    timeline_message_key,
    update_timeline_section,
)

logger = get_logger()


def create_incident_conversation(client: WebClient, incident_name: str):
    """Create an incident conversation channel.

    Args:
        client (WebClient): The Slack WebClient instance.
        incident_name (str): The name of the incident.

    Returns:
        dict: A dictionary containing the channel ID, channel name, and slug.
    """
    date_now = datetime.now().strftime("%Y-%m-%d")
    slug = f"{date_now} {incident_name}".strip().replace(" ", "-").lower()
    channel_name_prefix = "incident-dev-" if host_info().environment != "production" else "incident-"
    base_channel_name = channel_name_prefix + slug
    # Ensure base_channel_name is at most 80 chars
    if len(base_channel_name) > 80:
        base_channel_name = base_channel_name[:80]
    i = 0
    while True:
        if i == 0:
            attempt_channel_name = base_channel_name
        else:
            # Calculate the max length for the base part so that the suffix fits in 80 chars
            suffix = f"-{i}"
            max_base_length = 80 - len(suffix)
            truncated_base = base_channel_name[:max_base_length]
            attempt_channel_name = f"{truncated_base}{suffix}"
        try:
            response: SlackResponse = client.conversations_create(name=attempt_channel_name)
            if response.get("ok"):
                if i > 0:
                    slug = f"{slug}{suffix}"
                channel_details = response.get("channel")
                if not isinstance(channel_details, dict):
                    raise SlackApiError("Error creating the channel", response)
                channel_id = channel_details.get("id", "")
                channel_name = attempt_channel_name
                break
            elif response.get("error") != "name_taken":
                raise SlackApiError("Error creating the channel", response)
        except SlackApiError as e:
            # If the error is name_taken, continue to next attempt; otherwise, raise
            if hasattr(e, "response") and getattr(e.response, "data", {}).get("error") == "name_taken":
                pass  # Try next channel name
            else:
                raise
        i += 1
    return {"channel_id": channel_id, "channel_name": channel_name, "slug": slug}


# Make sure that we are listening only on floppy disk reaction
def is_floppy_disk(event: dict) -> bool:
    return bool(event["reaction"] == "floppy_disk")


# We need to ack all other reactions so that they don't get processed
def just_ack_the_rest_of_reaction_events():
    pass


def is_incident_channel(client: WebClient, channel_id: str, notify: bool = True) -> tuple[bool, bool]:
    """Check if the channel is an incident channel."""
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
        logger.error(
            "incident_channel_info_error",
            channel=channel_id,
            error=str(e),
        )
        raise e
    if notify and not is_incident:
        client.chat_postMessage(
            channel=channel_id,
            text="This channel is not an incident channel. Please use this command in an incident channel.",
        )
    return is_incident, is_dev_incident


def rearrange_by_datetime_ascending(text: str) -> str:
    matches = list(TIMELINE_ENTRY_PATTERN.finditer(text))
    if not matches:
        return text
    entries: dict[tuple[str, str], tuple[int, str]] = {}
    for index, match in enumerate(matches):
        key = timeline_message_key(match["url"])
        posted_at = (
            int(key[1])
            if key[0]
            else int(datetime.strptime(match["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("US/Eastern")).timestamp())
            * 1_000_000
        )
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries[key] = (posted_at, text[match.start() : end].rstrip("\n"))
    return (
        text[: matches[0].start()] + "\n".join(entry for _, entry in sorted(entries.values(), key=lambda entry: entry[0])) + "\n"
    )


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


def get_incident_document_id(client, channel_id):
    """
    Retrieve the incident report document ID from the incident channel.

    This function fetches the list of bookmarks for the specified channel
    and looks for a bookmark titled "Incident report". If found, it extracts
    the Google Docs document ID from the bookmark link.

    Parameters:
    - client: The client instance used to interact with the API.
    - channel_id: The ID of the channel to fetch bookmarks from.

    Returns:
    - document_id: The ID of the Google Docs incident report document, or an
      empty string if no such document is found.
    """
    document_id = ""
    response = client.bookmarks_list(channel_id=channel_id)
    if response["ok"]:
        for item in range(len(response["bookmarks"])):
            if response["bookmarks"][item]["title"] == "Incident report":
                document_id = incident_documents.extract_google_doc_id(response["bookmarks"][item]["link"])
                if document_id == "":
                    logger.error(
                        "incident_document_bookmark_not_found",
                        channel=channel_id,
                        error="No bookmark link for the incident document found",
                    )
    return document_id


def handle_reaction_added(client, ack, body):
    ack()
    # get the channel in which the reaction was used
    channel_id = body["event"]["item"]["channel"]
    # Get the channel name which requires us to use the conversations_info API call
    try:
        channel_name = client.conversations_info(channel=channel_id)["channel"]["name"]
    except SlackApiError:
        logger.error("incident_document_update_failed", channel=channel_id, action="save", message_ts=body["event"]["item"]["ts"])
        _notify_timeline_failure(client, body, "save", "")
        return

    # if the emoji added is a floppy disk emoji and we are in an incident channel, then add the message to the incident timeline
    if channel_name.startswith("incident-"):
        link = ""
        # get the message from the conversation
        try:
            # get the messages from the conversation and incident channel
            link = client.chat_getPermalink(channel=channel_id, message_ts=body["event"]["item"]["ts"])["permalink"]
            messages = return_messages(client, body, channel_id)

            # get the incident report document id from the incident channel
            document_id = get_incident_document_id(client, channel_id)
            if not document_id:
                raise ValueError("Incident report not found")

            for message in messages:
                # get the forwarded message and get the attachments appending the forwarded message to the original message
                message = handle_forwarded_messages(message)

                # get the message ts time
                message_ts = message["ts"]

                # convert the time which is now in epoch time to standard ET Time
                message_date_time = convert_epoch_to_datetime_est(message_ts)

                # get the user name from the message
                user = client.users_profile_get(user=message["user"])
                # get the full name of the user so that we include it into the timeline
                user_full_name = user["profile"]["real_name"]

                # handle any images in the messages
                message = handle_images_in_message(message)

                # if the message contains mentions to other slack users, replace those mentions with their name
                message = slack_users.replace_user_id_with_handle(client, message["text"])

                new_entry = f"\n ➡️ [{message_date_time}]({link}) {user_full_name}: {message}\n"

                def add_entry(content, link=link, new_entry=new_entry):
                    # if the message already exists in the timeline, then don't put it there again
                    if any(
                        timeline_message_key(match["url"]) == timeline_message_key(link)
                        for match in TIMELINE_ENTRY_PATTERN.finditer(content)
                    ):
                        return None
                    # append the new message and sort all the messages in ascending chronological order
                    return rearrange_by_datetime_ascending(content + new_entry)

                # rewrite the timeline section from the current state of the document
                result = update_timeline_section(document_id, add_entry)
                if not result.is_success:
                    _notify_timeline_failure(client, body, "save", link, result.error_code)
        except SlackApiError, ValueError:
            logger.error(
                "incident_document_update_failed",
                channel=channel_name,
                action="save",
                message_ts=body["event"]["item"]["ts"],
            )
            _notify_timeline_failure(client, body, "save", link)


# Execute this function when a reaction was removed
def handle_reaction_removed(client, ack, body):
    ack()
    # get the channel id
    channel_id = body["event"]["item"]["channel"]

    # Get the channel name which requires us to use the conversations_info API call
    try:
        result = client.conversations_info(channel=channel_id)
        channel_name = result["channel"]["name"]
    except SlackApiError:
        logger.error(
            "incident_document_update_failed", channel=channel_id, action="remove", message_ts=body["event"]["item"]["ts"]
        )
        _notify_timeline_failure(client, body, "remove", "")
        return

    if channel_name.startswith("incident-"):
        link = ""
        try:
            link = client.chat_getPermalink(channel=channel_id, message_ts=body["event"]["item"]["ts"])["permalink"]
            messages = return_messages(client, body, channel_id)

            if not messages:
                logger.warning(
                    "handle_reaction_removed_no_messages",
                    channel=channel_name,
                    error="No messages found",
                )
                _notify_timeline_failure(client, body, "remove", link)
                return
            # get the incident report document id from the incident channel
            document_id = get_incident_document_id(client, channel_id)
            if not document_id:
                raise ValueError("Incident report not found")

            message_found = False

            def remove_entry(content):
                nonlocal message_found
                matches = list(TIMELINE_ENTRY_PATTERN.finditer(content))
                spans = [
                    (match.start(), matches[index + 1].start() if index + 1 < len(matches) else len(content))
                    for index, match in enumerate(matches)
                    if timeline_message_key(match["url"]) == timeline_message_key(link)
                ]
                if not spans:
                    return None
                message_found = True
                for start, end in reversed(spans):
                    content = content[:start] + content[end:]
                return content

            # Remove the message and update the timeline content
            updated = update_timeline_section(document_id, remove_entry)
            if not updated.is_success:
                _notify_timeline_failure(client, body, "remove", link, updated.error_code)
            elif not message_found:
                logger.warning(
                    "handle_reaction_removed_message_not_found",
                    channel=channel_name,
                    error="Message not found in the timeline",
                )
                return
        except SlackApiError, ValueError:
            logger.error(
                "incident_document_update_failed",
                channel=channel_name,
                action="remove",
                message_ts=body["event"]["item"]["ts"],
            )
            _notify_timeline_failure(client, body, "remove", link)


# Function to return the messages from the conversation
def return_messages(client: WebClient, body: dict, channel_id: str) -> list[dict]:
    item = body["event"]["item"]
    if item.get("type", "message") != "message":
        raise ValueError("Reaction is not on a message")
    result = client.reactions_get(channel=channel_id, timestamp=item["ts"])
    message = result.get("message")
    if (
        not result.get("ok")
        or result.get("type") != "message"
        or not isinstance(message, dict)
        or message.get("ts") != item["ts"]
    ):
        raise ValueError("Reacted-to message unavailable")
    return [message]


def _notify_timeline_failure(client: WebClient, body: dict, action: str, link: str, error_code: str | None = None) -> None:
    event = body["event"]
    if not event.get("user"):
        logger.error("incident_timeline_notice_failed", channel=event["item"]["channel"], action=action, error="Missing actor")
        return
    # The reacting user's locale is not resolved here, so the notice carries both languages, as the stale nudge does.
    key = f"incident.timeline.{action}_{'unconfirmed' if error_code == ErrorCode.TIMEOUT else 'failed'}"
    text = "\n".join(
        i18n.t(key, locale=locale, link=link or i18n.t("incident.timeline.this_message", locale=locale))
        for locale in ("en-US", "fr-FR")
    )
    try:
        client.chat_postEphemeral(channel=event["item"]["channel"], user=event["user"], text=text)
    except SlackApiError:
        logger.error(
            "incident_timeline_notice_failed", channel=event["item"]["channel"], message_ts=event["item"]["ts"], action=action
        )


def archive_channel_action(client: WebClient, body, ack, respond):
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
        msg = f"<@{user}> has delayed scheduling and archiving this channel for 14 days."
        client.chat_update(channel=channel_id, text=msg, ts=body["message_ts"], attachments=[])
        log_to_sentinel("incident_channel_archive_delayed", body)
    elif action == "archive":
        # Call the close_incident function to update the incident document to closed, update the spreadsheet and archive the channel
        incident_helper.close_incident(client, channel_info, ack, respond)
        # log the event to sentinel
        log_to_sentinel("incident_channel_archived", body)
    elif action == "schedule_retro":
        channel_info["trigger_id"] = body["trigger_id"]
        schedule_retro.open_incident_retro_modal(client, channel_info, ack)
        # log the event to sentinel
        log_to_sentinel("incident_retro_scheduled", body)
