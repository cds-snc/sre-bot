import logging
from datetime import datetime
from integrations.sentinel import send_event
import re
import pytz

logging.basicConfig(level=logging.INFO)


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


def rearrange_by_datetime_ascending(text):
    # Split the text by lines
    lines = text.split("\n")

    # Temporary storage for multiline entries
    entries = []
    current_entry = []

    # Iterate over each line
    for line in lines:
        # Check if the line starts with a datetime format including 'ET'
        if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ET", line):
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
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ET):?[\s,]*(.*)", entry, re.DOTALL
        )
        if match:
            date_str, msg = match.groups()
            # Parse the datetime string (ignoring 'ET' for parsing)
            dt = datetime.strptime(date_str[:-3].strip(), "%Y-%m-%d %H:%M:%S")
            dated_entries.append((dt, msg))

    # Sort the entries by datetime in ascending order
    sorted_entries = sorted(dated_entries, key=lambda x: x[0], reverse=False)

    # Reformat the entries back into strings, including 'ET'
    sorted_text = "\n".join(
        [
            f"{entry[0].strftime('%Y-%m-%d %H:%M:%S')} ET {entry[1]}"
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


# Function to replace the user id with the user handle in a message:w
def replace_user_id_with_handle(user_handle, message):
    if not user_handle or not message:
        logging.error("User handle or message is empty or None")
        return None

    user_id_pattern = r"<@\w+>"
    if re.search(user_id_pattern, message):
        message = re.sub(user_id_pattern, user_handle, message)
    return message
