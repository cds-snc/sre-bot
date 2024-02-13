import re
from datetime import datetime
import pytz


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
