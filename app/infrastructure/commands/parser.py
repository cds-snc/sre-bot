"""Command parsing and validation."""

from typing import Any, Dict, List, Tuple
import re

from core.logging import get_module_logger
from infrastructure.commands.models import (
    Command,
    ArgumentType,
    ParsedCommand,
)

logger = get_module_logger()


class CommandParseError(Exception):
    """Error during command parsing."""

    pass


class CommandParser:
    """Parse command strings into structured arguments.

    Handles:
    - Positional arguments
    - Flag arguments (--flag, --key=value)
    - Quoted strings with proper escaping
    - Type validation and coercion
    - Required argument validation

    Example:
        parser = CommandParser()

        cmd = Command(
            name="add",
            handler=lambda: None,
            args=[
                Argument("email", type=ArgumentType.EMAIL),
                Argument("--force", type=ArgumentType.BOOLEAN, flag=True)
            ]
        )

        result = parser.parse(cmd, ["alice@example.com", "--force"])
        # ParsedCommand(
        #     command=cmd,
        #     args={"email": "alice@example.com", "force": True},
        #     raw_text="alice@example.com --force"
        # )
    """

    def parse(self, command: Command, tokens: List[str]) -> ParsedCommand:
        """Parse command tokens into structured arguments.

        Args:
            command: Command definition with argument schemas
            tokens: Command tokens to parse

        Returns:
            ParsedCommand with validated arguments

        Raises:
            CommandParseError: If parsing or validation fails
        """
        raw_text = " ".join(tokens)

        try:
            positional, flags = self._split_tokens(tokens)
            args = self._parse_arguments(command, positional, flags)

            return ParsedCommand(
                command=command,
                args=args,
                raw_text=raw_text,
            )
        except CommandParseError as e:
            logger.warning(
                "command_parse_error",
                command=command.name,
                raw_text=raw_text,
                error=str(e),
            )
            raise

    def _split_tokens(self, tokens: List[str]) -> Tuple[List[str], Dict[str, str]]:
        """Split tokens into positional args and flags.

        Handles:
        - Quoted strings: "hello world" -> hello world
        - Flag with value: --key=value -> {key: value}
        - Flag without value: --verbose -> {verbose: "true"}

        Args:
            tokens: Raw tokens from user input

        Returns:
            Tuple of (positional_args, flags_dict)

        Raises:
            CommandParseError: If quotes are mismatched
        """
        positional = []
        flags = {}
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Handle quoted strings
            if token.startswith('"') or token.startswith("'"):
                quote_char = token[0]
                if token.endswith(quote_char) and len(token) > 1:
                    # Single token quoted string
                    positional.append(self._unquote(token))
                else:
                    # Multi-token quoted string
                    parts = [token[1:]]
                    i += 1
                    while i < len(tokens):
                        parts.append(tokens[i])
                        if tokens[i].endswith(quote_char):
                            parts[-1] = parts[-1][:-1]
                            break
                        i += 1
                    else:
                        raise CommandParseError(f"Unclosed quote: {quote_char}")
                    positional.append(" ".join(parts))
            # Handle flags
            elif token.startswith("--"):
                if "=" in token:
                    key, value = token[2:].split("=", 1)
                    flags[key] = self._unquote(value)
                else:
                    key = token[2:]
                    flags[key] = "true"
            # Positional argument
            else:
                positional.append(token)

            i += 1

        return positional, flags

    def _unquote(self, value: str) -> str:
        """Remove quotes from value.

        Args:
            value: Possibly quoted string

        Returns:
            Unquoted string
        """
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        return value

    def _parse_arguments(
        self,
        command: Command,
        positional: List[str],
        flags: Dict[str, str],
    ) -> Dict[str, Any]:
        """Parse and validate arguments against command definition.

        Args:
            command: Command definition with schemas
            positional: Positional argument values
            flags: Flag argument values

        Returns:
            Dict of parsed and coerced arguments

        Raises:
            CommandParseError: If required args missing, invalid choices, type errors
        """
        result = {}
        pos_index = 0

        # Process positional arguments
        for arg in command.args:
            if arg.flag:
                continue

            if pos_index < len(positional):
                value = positional[pos_index]
                pos_index += 1
            elif arg.required:
                raise CommandParseError(f"Missing required argument: {arg.name}")
            elif arg.default is not None:
                value = arg.default
            else:
                continue

            result[arg.name] = self._coerce_type(value, arg.type, arg.name)

            # Validate choices
            if arg.choices and result[arg.name] not in arg.choices:
                choices_str = ", ".join(str(c) for c in arg.choices)
                raise CommandParseError(
                    f"Invalid value for {arg.name}: {result[arg.name]}. "
                    f"Choose from: {choices_str}"
                )

        # Check extra positional arguments
        if pos_index < len(positional):
            raise CommandParseError(
                f"Extra arguments: {' '.join(positional[pos_index:])}"
            )

        # Process flag arguments
        for arg in command.args:
            if not arg.flag:
                continue

            flag_key = arg.name[2:]  # Remove '--'
            if flag_key in flags:
                value = flags[flag_key]
                result[arg.name] = self._coerce_type(value, arg.type, arg.name)
            elif arg.required:
                raise CommandParseError(f"Missing required flag: {arg.name}")
            elif arg.default is not None:
                result[arg.name] = arg.default

        return result

    def _coerce_type(self, value: str, arg_type: ArgumentType, name: str) -> Any:
        """Coerce string value to argument type.

        Args:
            value: String value to coerce
            arg_type: Target ArgumentType
            name: Argument name (for error messages)

        Returns:
            Coerced value

        Raises:
            CommandParseError: If coercion fails
        """
        try:
            if arg_type == ArgumentType.STRING:
                return value
            elif arg_type == ArgumentType.INTEGER:
                return int(value)
            elif arg_type == ArgumentType.FLOAT:
                return float(value)
            elif arg_type == ArgumentType.BOOLEAN:
                if value.lower() in ("true", "1", "yes", "on"):
                    return True
                elif value.lower() in ("false", "0", "no", "off"):
                    return False
                else:
                    raise CommandParseError(
                        f"Invalid boolean for {name}: {value}. Use true/false."
                    )
            elif arg_type == ArgumentType.EMAIL:
                # Basic email validation
                if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value):
                    raise CommandParseError(f"Invalid email for {name}: {value}")
                return value
            else:
                return value
        except (ValueError, TypeError) as e:
            raise CommandParseError(
                f"Cannot convert {name}={value} to {arg_type.value}: {str(e)}"
            )
