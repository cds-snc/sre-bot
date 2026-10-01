"""Business logic for the rant command.

Platform-agnostic transformation of user text into a bold, uppercase shout.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class UserIdentity:
    """The name and avatar a rant is posted under."""

    display_name: str
    icon_url: str


@runtime_checkable
class UserIdentityLookup(Protocol):
    """Behavior contract for resolving the identity a rant is posted under."""

    def lookup_user_identity(self, user_id: str) -> UserIdentity | None:
        """Return the user's name and avatar, or ``None`` when either is unavailable."""
        ...


def format_rant(text: str) -> str:
    """Format text as a bold, uppercase Slack message.

    Args:
        text: Raw user-supplied text.

    Returns:
        The text uppercased and wrapped in Slack bold markers.
    """
    return f"*{text.upper()}*"
