"""Command argument parser with quote-aware tokenization.

Handles:
- Flag parsing (--managed)
- Option parsing (--role OWNER)
- Positional arguments (group_id)
- Multiple values (--role OWNER,MEMBER)
- Type validation (email, integer, choice, etc.)
- Required/optional validation
- Default value substitution
"""

from typing import Dict, List, Any, Optional

from infrastructure.platforms.parsing.models import (
    Argument,
    ArgumentType,
    ArgumentParsingError,
)


class CommandArgumentParser:
    """Parses raw command text into structured arguments.

    Critical: Uses quote-aware tokenization to preserve quoted values
    containing spaces, special characters, and escape sequences.
    """

    def __init__(self, arguments: List[Argument]):
        """Initialize parser with argument definitions.

        Args:
            arguments: List of Argument definitions to parse for.
        """
        self.arguments = arguments
        self._build_lookup()

    def _build_lookup(self) -> None:
        """Build fast lookup maps for flags, options, and positional args."""
        self._flags: Dict[str, Argument] = {}  # name -> Argument for boolean flags
        self._options: Dict[str, Argument] = {}  # name -> Argument for options
        self._positional: List[Argument] = []  # List[Argument] in order
        self._aliases: Dict[str, str] = {}  # alias -> canonical_name

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
            raw_text: Raw command text (e.g., "--managed --role OWNER group_123").

        Returns:
            Dict of parsed arguments keyed by argument name.

        Raises:
            ArgumentParsingError: If parsing or validation fails.

        Example:
            >>> parser = CommandArgumentParser([
            ...     Argument(name="--managed", type=ArgumentType.BOOLEAN),
            ...     Argument(name="--role", type=ArgumentType.STRING),
            ...     Argument(name="group_id", type=ArgumentType.STRING, required=True),
            ... ])
            >>> result = parser.parse("--managed --role OWNER group_123")
            >>> result
            {'--managed': True, '--role': 'OWNER', 'group_id': 'group_123'}
        """
        tokens = self._tokenize(raw_text) if raw_text and raw_text.strip() else []
        parsed: Dict[str, Any] = {}
        positional_index = 0
        i = 0

        # Parse flags and options
        while i < len(tokens):
            token = tokens[i]

            if token.startswith("--") or token.startswith("-"):
                # Resolve alias to canonical name
                canonical_name = self._aliases.get(token, token)

                if canonical_name in self._flags:
                    # Boolean flag
                    arg_def = self._flags[canonical_name]
                    parsed[arg_def.name] = True
                    i += 1

                elif canonical_name in self._options:
                    # Option with value - next token is the value
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
        """Tokenize command text respecting quotes.

        CRITICAL: This tokenizer MUST preserve quoted values intact.
        Do NOT use text.split() which destroys quote-wrapped arguments.

        Supports:
        - Double quotes: --flag "value with spaces"
        - Single quotes: --flag 'value with spaces'
        - Backticks: --flag `value with spaces`
        - Escaped quotes: --flag "value with \\"nested\\" quotes"
        - Mixed quotes: --flag "outer 'inner' text"
        - Empty strings: --flag ""

        Algorithm:
        1. Iterate character by character
        2. Track quote state (inside/outside quotes, quote type)
        3. Accumulate characters until delimiter (space outside quotes)
        4. Preserve all whitespace inside quotes
        5. Strip outer quotes from final token
        6. Track if we just finished a quoted section to emit empty strings

        Example:
            >>> tokenize('--role "Senior Manager" --managed')
            ['--role', 'Senior Manager', '--managed']

            >>> tokenize("--justification 'Emergency: incident #123'")
            ['--justification', 'Emergency: incident #123']

            >>> tokenize('--message "He said \\"hello\\" to me"')
            ['--message', 'He said "hello" to me']

            >>> tokenize('--message ""')
            ['--message', '']

        Returns:
            List of tokens with quotes stripped and values preserved.
        """
        tokens: List[str] = []
        current_token: List[str] = []
        in_quotes = False
        quote_char: Optional[str] = None
        escaped = False
        was_quoted = False  # Track if we just finished a quoted section

        for char in text:
            # Handle escape sequences
            if escaped:
                # Add the escaped character without the backslash
                current_token.append(char)
                escaped = False
                continue

            if char == "\\":
                # Next character is escaped - set flag but don't add backslash
                escaped = True
                continue

            # Quote handling
            if char in ('"', "'", "`"):
                if not in_quotes:
                    # Start of quoted section
                    in_quotes = True
                    quote_char = char
                    was_quoted = True
                    # Don't add the opening quote to token
                elif char == quote_char:
                    # End of quoted section (matching quote)
                    in_quotes = False
                    quote_char = None
                    # Don't add the closing quote to token
                else:
                    # Different quote type inside quotes - treat as literal
                    current_token.append(char)
                continue

            # Whitespace handling
            if char.isspace():
                if in_quotes:
                    # Preserve whitespace inside quotes
                    current_token.append(char)
                else:
                    # End of token (outside quotes)
                    # Add token if: has content OR just finished a quoted section (empty string)
                    if current_token or was_quoted:
                        tokens.append("".join(current_token))
                        current_token = []
                        was_quoted = False
            else:
                # Regular character
                current_token.append(char)
                was_quoted = False

        # Add final token
        # Include if: has content OR just finished a quoted section (empty string)
        if current_token or was_quoted:
            tokens.append("".join(current_token))

        return tokens

    def _validate_value(self, value: str, arg_def: Argument) -> Any:
        """Validate and convert value to correct type.

        Args:
            value: The value to validate.
            arg_def: The argument definition.

        Returns:
            Validated/converted value of the appropriate type.

        Raises:
            ArgumentParsingError: If validation fails.
        """
        if arg_def.type == ArgumentType.EMAIL:
            # Simple email validation
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
            # Parse comma-separated values
            return [v.strip() for v in value.split(",") if v.strip()]

        # STRING type - no additional validation
        return value

    def _validate_required(self, parsed: Dict[str, Any]) -> None:
        """Check all required arguments are present.

        Args:
            parsed: The parsed arguments dict.

        Raises:
            ArgumentParsingError: If a required argument is missing.
        """
        for arg in self.arguments:
            if arg.required and arg.name not in parsed:
                raise ArgumentParsingError(
                    argument=arg.name,
                    message=f"Required argument missing: {arg.name}",
                    suggestion=arg.description,
                )

    def _apply_defaults(self, parsed: Dict[str, Any]) -> None:
        """Apply default values for missing arguments.

        Args:
            parsed: The parsed arguments dict (modified in place).
        """
        for arg in self.arguments:
            if arg.name not in parsed and arg.default is not None:
                parsed[arg.name] = arg.default
