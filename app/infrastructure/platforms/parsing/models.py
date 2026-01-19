"""Argument definition models for command parsing.

Provides:
- ArgumentType: Enum of supported argument types
- Argument: Definition of a single command argument (positional, flag, or option)
- ArgumentParsingError: Exception raised when parsing fails
"""

from enum import Enum
from typing import Optional, List, Any
from dataclasses import dataclass


class ArgumentType(str, Enum):
    """Supported argument types for parsing and validation."""

    STRING = "string"
    EMAIL = "email"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    CHOICE = "choice"
    CSV = "csv"  # Comma-separated values


@dataclass
class Argument:
    """Definition of a single command argument.

    Supports:
    - Positional args: name="group_id"
    - Flags: name="--managed" (automatically boolean)
    - Options: name="--role" (takes a value)
    - Aliases: name="--role,-r" (alternative flag names)

    Attributes:
        name: Argument name (e.g., 'group_id', '--role', '--managed').
        type: Argument type for validation. Defaults to STRING.
        required: Whether argument is required. Defaults to False.
        description: Human-readable description.
        description_key: i18n translation key for description.
        choices: Valid choices for CHOICE type.
        default: Default value if not provided.
        aliases: Alternative names (e.g., ['-r'] for '--role').
        allow_multiple: Whether argument can be specified multiple times.
    """

    name: str
    """Argument name (e.g., 'group_id', '--role', '--managed')"""

    type: ArgumentType = ArgumentType.STRING
    """Argument type for validation"""

    required: bool = False
    """Whether argument is required"""

    description: str = ""
    """Human-readable description"""

    description_key: Optional[str] = None
    """i18n translation key"""

    choices: Optional[List[str]] = None
    """Valid choices (for CHOICE type)"""

    default: Optional[Any] = None
    """Default value if not provided"""

    aliases: Optional[List[str]] = None
    """Alternative names (e.g., ['-r'] for '--role')"""

    allow_multiple: bool = False
    """Whether argument can be specified multiple times"""

    @property
    def is_flag(self) -> bool:
        """Is this a boolean flag (--managed)?"""
        return self.type == ArgumentType.BOOLEAN and self.name.startswith("--")

    @property
    def is_option(self) -> bool:
        """Is this an option that takes a value (--role VALUE)?"""
        return self.name.startswith("--") and not self.is_flag

    @property
    def is_positional(self) -> bool:
        """Is this a positional argument?"""
        return not self.name.startswith("--")

    def get_canonical_name(self) -> str:
        """Get the canonical name (primary flag/option name)."""
        # For flags/options, it's the first part before any aliases
        # For positionals, just return the name
        return self.name.split(",")[0].strip()


@dataclass
class ArgumentParsingError(Exception):
    """Raised when argument parsing fails.

    Attributes:
        argument: The argument that failed to parse.
        message: Error message.
        suggestion: Optional suggestion for fixing the error.
    """

    argument: str
    message: str
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        """Format error message for display."""
        result = f"Error parsing {self.argument}: {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result
