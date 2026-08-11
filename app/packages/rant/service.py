"""Business logic for the rant command.

Platform-agnostic transformation of user text into a bold, uppercase shout.
"""


def format_rant(text: str) -> str:
    """Format text as a bold, uppercase Slack message.

    Args:
        text: Raw user-supplied text.

    Returns:
        The text uppercased and wrapped in Slack bold markers.
    """
    return f"*{text.upper()}*"
