"""Google Meet Module.

This module provides a function to start a Google Meet session.

Functions:
    create_google_meet(title: str) -> str:
        Starts a Google Meet session and returns the URL of the session.
"""

import re
from datetime import datetime


def create_google_meet(title=None):
    """
    Starts a Google Meet session.

    Args:
        title (str, optional): The title of the session.

    Returns:
        str: The URL of the Google Meet session.
    """
    # if title is None, set it to the current date
    if title is None:
        title = f"Meeting-Rencontre-{datetime.now().strftime('%Y-%m-%d')}"

    # replace spaces with dashes
    title = title.replace(" ", "-")
    # remove any special characters
    title = re.sub("[^0-9a-zA-Z]+", "-", title)
    title = title.strip("-")

    meeting_link = f"https://g.co/meet/{title}"
    if len(meeting_link) > 78:
        meeting_link = meeting_link[:78]

    return meeting_link
