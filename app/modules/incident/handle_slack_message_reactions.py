import re
from datetime import datetime
import pytz


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
