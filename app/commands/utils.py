import logging
import time
from datetime import datetime, timedelta
from integrations.sentinel import send_event
import re
import pytz

logging.basicConfig(level=logging.INFO)


# Get all incident channels
def get_incident_channels(client):
    channels = []
    cursor = None

    # Execute while the next_cursor is not empty. We need to iterate through the collection limiting to a max of 100 channels
    # at a time. The cursor is used to keep track of the current position in the collection. This is due to Slack's pagination
    # and the way it hanles retrieval of channels.
    while True:
        response = client.conversations_list(
            exclude_archived=True, limit=100, types="public_channel", cursor=cursor
        )

        # if we did not get a successful response, break out of the loop
        if not response.get("ok"):
            break

        # filter the channels to only include incident channels
        for channel in response.get("channels", []):
            if channel["name"].startswith("incident-20"):
                channels.append(channel)

        # get the next cursor
        cursor = response.get("response_metadata", {}).get("next_cursor")

        # if the cursor is empty, break out of the loop
        if not cursor:
            break

    # return the list of incident channels
    return channels


def get_messages_in_time_period(client, channel_id, time_delta):
    client.conversations_join(channel=channel_id)
    messages = client.conversations_history(
        channel=channel_id,
        limit=10,
        oldest=time.mktime((datetime.now() - time_delta).timetuple()),
    )
    if messages["ok"]:
        return list(
            filter(lambda x: "team" in x, messages["messages"])
        )  # Return only messages from users
    else:
        return []


def get_stale_channels(client):
    STALE_PERIOD = timedelta(days=14)
    now = datetime.now()
    stale_channels = []
    channels = list(
        filter(
            lambda x: x["created"] < time.mktime((now - STALE_PERIOD).timetuple()),
            get_incident_channels(client),
        )
    )
    stale_channels = list(
        filter(
            lambda x: len(get_messages_in_time_period(client, x["id"], STALE_PERIOD))
            == 0,
            channels,
        )
    )
    return stale_channels


def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    logging.info(f"Ops msg: {message}")
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def log_to_sentinel(event, message):
    payload = {"event": event, "message": message}
    if send_event(payload):
        logging.info(f"Sentinel event sent: {payload}")
    else:
        logging.error(f"Sentinel event failed: {payload}")


def parse_command(command):
    """
    Parses a command string into a list of arguments.
    """
    args = []
    arg = ""
    in_quote = False
    for char in command:
        if char == '"':
            if in_quote:
                args.append(arg)
                arg = ""
                in_quote = False
            else:
                in_quote = True
        elif char == " " and not in_quote:
            args.append(arg)
            arg = ""
        else:
            arg += char
    if arg:
        args.append(arg)
    return args


def get_user_locale(user_id, client):
    """
    Returns the user locale from a command's user_id if valid, "en-US" as default otherwise
    """
    default_locale = "en-US"
    supported_locales = ["en-US", "fr-FR"]
    user_locale = client.users_info(user=user_id, include_locale=True)
    if user_locale["ok"] and (user_locale["user"]["locale"] in supported_locales):
        return user_locale["user"]["locale"]
    return default_locale


def rearrange_by_datetime_ascending(text):
    # Split the text by lines
    lines = text.split("\n")

    # Temporary storage for multiline entries
    entries = []
    current_entry = []

    # Iterate over each line
    for line in lines:
        # Check if the line starts with a datetime format including 'EST'
        if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} EST", line):
            if current_entry:
                # Combine the lines in current_entry and add to entries
                entries.append("\n".join(current_entry))
                current_entry = [line]
            else:
                current_entry.append(line)
        else:
            # If not a datetime, it's a continuation of the previous message
            current_entry.append(line)

    # Add the last entry
    if current_entry:
        if current_entry.__len__() > 1:
            # that means we have a multiline entry
            joined_current_entry = "\n".join(current_entry)
            entries.append(joined_current_entry)
        else:
            entries.append("\n".join(current_entry))

    # Now extract date, time, and message from each entry
    dated_entries = []
    for entry in entries:
        match = re.match(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} EST):?[\s,]*(.*)", entry, re.DOTALL
        )
        if match:
            date_str, msg = match.groups()
            # Parse the datetime string (ignoring 'EST' for parsing)
            dt = datetime.strptime(date_str[:-4].strip(), "%Y-%m-%d %H:%M:%S")
            dated_entries.append((dt, msg))

    # Sort the entries by datetime in ascending order
    sorted_entries = sorted(dated_entries, key=lambda x: x[0], reverse=False)

    # Reformat the entries back into strings, including 'EST'
    sorted_text = "\n".join(
        [
            f"{entry[0].strftime('%Y-%m-%d %H:%M:%S')} EST {entry[1]}"
            for entry in sorted_entries
        ]
    )

    return sorted_text


def convert_epoch_to_datetime_est(epoch_time):
    """
    Convert an epoch time to a standard date/time format in Eastern Standard Time (EST).

    Args:
    epoch_time (float): The epoch time.

    Returns:
    str: The corresponding date and time in the format YYYY-MM-DD HH:MM:SS EST.
    """
    # Define the Eastern Standard Timezone
    est = pytz.timezone("US/Eastern")

    # Convert epoch time to a datetime object in UTC
    utc_datetime = datetime.utcfromtimestamp(float(epoch_time))

    # Convert UTC datetime object to EST
    est_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(est)

    # Format the datetime object to a string in the desired format with 'EST' at the end
    return est_datetime.strftime("%Y-%m-%d %H:%M:%S") + " EST"


def extract_google_doc_id(url):
    # if the url is empty or None, then log an error
    if not url:
        logging.error("URL is empty or None")
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
