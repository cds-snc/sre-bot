"""Slack command argument parsing.

Quote-aware tokenization and type validation for slash command arguments.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ArgumentType(str, Enum):
    """Supported argument types."""

    STRING = "string"
    EMAIL = "email"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    CHOICE = "choice"
    CSV = "csv"


@dataclass
class Argument:
    """Command argument definition."""

    name: str
    type: ArgumentType = ArgumentType.STRING
    required: bool = False
    description: str = ""
    description_key: Optional[str] = None
    choices: Optional[List[str]] = None
    default: Optional[Any] = None
    aliases: Optional[List[str]] = None
    allow_multiple: bool = False

    @property
    def is_flag(self) -> bool:
        """Is this a boolean flag?"""
        return self.type == ArgumentType.BOOLEAN and self.name.startswith("--")

    @property
    def is_option(self) -> bool:
        """Is this an option that takes a value?"""
        return self.name.startswith("--") and not self.is_flag

    @property
    def is_positional(self) -> bool:
        """Is this a positional argument?"""
        return not self.name.startswith("--")

    def get_canonical_name(self) -> str:
        """Get canonical name (primary flag/option name)."""
        return self.name.split(",")[0].strip()


@dataclass
class ArgumentParsingError(Exception):
    """Raised when argument parsing fails."""

    argument: str
    message: str
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        """Format error for display."""
        result = f"Error parsing {self.argument}: {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result


class CommandArgumentParser:
    """Parses raw command text into structured arguments.

    Uses quote-aware tokenization to preserve arguments with spaces.
    """

    def __init__(self, arguments: List[Argument]):
        """Initialize with argument definitions."""
        self.arguments = arguments
        self._build_lookup()

    def _build_lookup(self) -> None:
        """Build lookup maps for flags, options, and positional args."""
        self._flags: Dict[str, Argument] = {}
        self._options: Dict[str, Argument] = {}
        self._positional: List[Argument] = []
        self._aliases: Dict[str, str] = {}

        for arg in self.arguments:
            canonical_name = arg.get_canonical_name()

            if arg.is_flag:
                self._flags[canonical_name] = arg
                if arg.aliases:
                    for alias in arg.aliases:
                        self._aliases[alias.strip()] = canonical_name

            elif arg.is_option:
                self._options[canonical_name] = arg
                if arg.aliases:
                    for alias in arg.aliases:
                        self._aliases[alias.strip()] = canonical_name
            else:
                self._positional.append(arg)

    def parse(self, raw_text: str) -> Dict[str, Any]:
        """Parse raw command text into structured arguments.

        Args:
            raw_text: Raw command text (e.g., "--managed --role OWNER group_123")

        Returns:
            Dict of parsed arguments

        Raises:
            ArgumentParsingError: If parsing or validation fails
        """
        tokens = self._tokenize(raw_text) if raw_text and raw_text.strip() else []
        parsed: Dict[str, Any] = {}
        positional_index = 0
        i = 0

        # Parse flags and options
        while i < len(tokens):
            token = tokens[i]

            if token.startswith("--") or token.startswith("-"):
                canonical_name = self._aliases.get(token, token)

                if canonical_name in self._flags:
                    arg_def = self._flags[canonical_name]
                    parsed[arg_def.name] = True
                    i += 1

                elif canonical_name in self._options:
                    if i + 1 >= len(tokens):
                        arg_def = self._options[canonical_name]
                        raise ArgumentParsingError(
                            argument=arg_def.name,
                            message=f"Expected value after {arg_def.name}",
                        )

                    arg_def = self._options[canonical_name]
                    value = tokens[i + 1]
                    validated_value = self._validate_value(value, arg_def)

                    if arg_def.allow_multiple:
                        if arg_def.name not in parsed:
                            parsed[arg_def.name] = []
                        parsed[arg_def.name].append(validated_value)
                    else:
                        parsed[arg_def.name] = validated_value

                    i += 2

                else:
                    raise ArgumentParsingError(
                        argument=token,
                        message=f"Unknown option: {token}",
                        suggestion="Check the command help for valid options",
                    )
            else:
                # Positional argument
                if positional_index >= len(self._positional):
                    raise ArgumentParsingError(
                        argument=token,
                        message="Too many positional arguments",
                    )

                arg_def = self._positional[positional_index]
                validated_value = self._validate_value(token, arg_def)

                if arg_def.allow_multiple:
                    if arg_def.name not in parsed:
                        parsed[arg_def.name] = []
                    parsed[arg_def.name].append(validated_value)
                else:
                    parsed[arg_def.name] = validated_value

                positional_index += 1
                i += 1

        # Validate required arguments
        self._validate_required(parsed)

        # Apply defaults
        self._apply_defaults(parsed)

        return parsed

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize respecting quotes. Preserves arguments with spaces."""
        tokens: List[str] = []
        current_token: List[str] = []
        in_quotes = False
        quote_char: Optional[str] = None
        escaped = False
        was_quoted = False

        for char in text:
            if escaped:
                current_token.append(char)
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char in ('"', "'", "`"):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                    was_quoted = True
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current_token.append(char)
                continue

            if char.isspace():
                if in_quotes:
                    current_token.append(char)
                else:
                    if current_token or was_quoted:
                        tokens.append("".join(current_token))
                        current_token = []
                        was_quoted = False
            else:
                current_token.append(char)
                was_quoted = False

        if current_token or was_quoted:
            tokens.append("".join(current_token))

        return tokens

    def _validate_value(self, value: str, arg_def: Argument) -> Any:
        """Validate and convert value to correct type."""
        if arg_def.type == ArgumentType.EMAIL:
            if "@" not in value or "." not in value.split("@")[1]:
                raise ArgumentParsingError(
                    argument=arg_def.name,
                    message=f"Invalid email format: {value}",
                    suggestion="Expected format: user@example.com",
                )
            return value

        elif arg_def.type == ArgumentType.INTEGER:
            try:
                return int(value)
            except ValueError:
                raise ArgumentParsingError(
                    argument=arg_def.name,
                    message=f"Expected integer, got: {value}",
                )

        elif arg_def.type == ArgumentType.CHOICE:
            if value not in (arg_def.choices or []):
                choices_str = ", ".join(arg_def.choices or [])
                raise ArgumentParsingError(
                    argument=arg_def.name,
                    message=f"Invalid choice: {value}",
                    suggestion=f"Valid choices: {choices_str}",
                )
            return value

        elif arg_def.type == ArgumentType.CSV:
            return [v.strip() for v in value.split(",") if v.strip()]

        return value

    def _validate_required(self, parsed: Dict[str, Any]) -> None:
        """Check all required arguments are present."""
        for arg in self.arguments:
            if arg.required and arg.name not in parsed:
                raise ArgumentParsingError(
                    argument=arg.name,
                    message=f"Required argument missing: {arg.name}",
                    suggestion=arg.description,
                )

    def _apply_defaults(self, parsed: Dict[str, Any]) -> None:
        """Apply default values for missing arguments."""
        for arg in self.arguments:
            if arg.name not in parsed and arg.default is not None:
                parsed[arg.name] = arg.default


__all__ = [
    "ArgumentType",
    "Argument",
    "ArgumentParsingError",
    "CommandArgumentParser",
]
