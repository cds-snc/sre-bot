"""Platform-agnostic response models for command handlers."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ButtonStyle(str, Enum):
    """Button style options.

    Attributes:
        DEFAULT: Default button style.
        PRIMARY: Primary action button style.
        DANGER: Dangerous action button style (destructive).
    """

    DEFAULT = "default"
    PRIMARY = "primary"
    DANGER = "danger"


@dataclass
class Button:
    """Platform-agnostic button representation.

    Represents an interactive button that can be rendered in various platforms.

    Attributes:
        text: Button label text displayed to the user.
        action_id: Unique identifier for button action handling.
        style: Visual style (default, primary, danger).
        value: Optional value passed with button click event.
    """

    text: str
    action_id: str
    style: ButtonStyle = ButtonStyle.DEFAULT
    value: Optional[str] = None


@dataclass
class Field:
    """Platform-agnostic field representation (key-value pair).

    Represents a labeled value that can be displayed in various formats
    depending on the platform rendering it.

    Attributes:
        title: Field title/label text.
        value: Field value/content text.
        short: Display inline (side-by-side) if True, full-width if False.
    """

    title: str
    value: str
    short: bool = False


@dataclass
class Card:
    """Platform-agnostic card/embed representation.

    Represents a rich message card with optional fields, buttons, images,
    and footer that can be rendered in various platforms.

    Attributes:
        title: Card title text.
        text: Main card text content.
        color: Hex color code for card accent (e.g., "#36a64f").
        fields: List of key-value fields to display.
        buttons: List of action buttons.
        footer: Optional footer text.
        image_url: Optional URL to card image.
    """

    title: str
    text: str
    color: str = "#36a64f"
    fields: List[Field] = field(default_factory=list)
    buttons: List[Button] = field(default_factory=list)
    footer: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class ErrorMessage:
    """Platform-agnostic error message representation.

    Represents an error state that should be communicated to the user
    in a visually distinct way.

    Attributes:
        message: Error message text displayed to the user.
        details: Optional detailed error information or traceback.
        error_code: Optional error code for debugging and tracking.
    """

    message: str
    details: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class SuccessMessage:
    """Platform-agnostic success message representation.

    Represents a successful operation that should be communicated to the user
    in a visually distinct way.

    Attributes:
        message: Success message text displayed to the user.
        details: Optional additional details about the success.
    """

    message: str
    details: Optional[str] = None
