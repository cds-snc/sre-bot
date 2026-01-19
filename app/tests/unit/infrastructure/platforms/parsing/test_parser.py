"""Unit tests for CommandArgumentParser.

Tests argument parsing including:
- Flag parsing (--managed)
- Option parsing (--role OWNER)
- Positional arguments (group_id)
- Multiple values (--role OWNER,MEMBER)
- Type validation (email, integer, choice, etc.)
- Required/optional validation
- Default value substitution
- Error handling
"""

import pytest

from infrastructure.platforms.parsing import (
    Argument,
    ArgumentType,
    ArgumentParsingError,
    CommandArgumentParser,
)


class TestFlagParsing:
    """Test boolean flag parsing."""

    def test_parse_single_flag(self):
        """Test parsing a single boolean flag."""
        parser = CommandArgumentParser(
            [Argument(name="--managed", type=ArgumentType.BOOLEAN)]
        )
        result = parser.parse("--managed")
        assert result["--managed"] is True

    def test_parse_flag_absent(self):
        """Test flag absent from input."""
        parser = CommandArgumentParser(
            [Argument(name="--managed", type=ArgumentType.BOOLEAN)]
        )
        result = parser.parse("")
        assert "--managed" not in result

    def test_parse_multiple_flags(self):
        """Test multiple boolean flags."""
        parser = CommandArgumentParser(
            [
                Argument(name="--managed", type=ArgumentType.BOOLEAN),
                Argument(name="--active", type=ArgumentType.BOOLEAN),
            ]
        )
        result = parser.parse("--managed --active")
        assert result["--managed"] is True
        assert result["--active"] is True

    def test_parse_flag_with_shorthand(self):
        """Test flag with shorthand alias."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="--managed",
                    type=ArgumentType.BOOLEAN,
                    aliases=["-m"],
                )
            ]
        )
        result = parser.parse("-m")
        assert result["--managed"] is True


class TestOptionParsing:
    """Test option (flag with value) parsing."""

    def test_parse_single_option(self):
        """Test parsing a single option."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING)]
        )
        result = parser.parse("--role OWNER")
        assert result["--role"] == "OWNER"

    def test_parse_option_missing_value(self):
        """Test error when option value is missing."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("--role")
        assert "--role" in str(exc.value)

    def test_parse_multiple_options(self):
        """Test multiple options."""
        parser = CommandArgumentParser(
            [
                Argument(name="--role", type=ArgumentType.STRING),
                Argument(name="--status", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse("--role OWNER --status active")
        assert result["--role"] == "OWNER"
        assert result["--status"] == "active"

    def test_parse_option_with_shorthand(self):
        """Test option with shorthand alias."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="--role",
                    type=ArgumentType.STRING,
                    aliases=["-r"],
                )
            ]
        )
        result = parser.parse("-r OWNER")
        assert result["--role"] == "OWNER"

    def test_parse_option_with_quoted_value(self):
        """Test option with quoted value."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "Hello world"')
        assert result["--message"] == "Hello world"


class TestPositionalParsing:
    """Test positional argument parsing."""

    def test_parse_single_positional(self):
        """Test single positional argument."""
        parser = CommandArgumentParser(
            [Argument(name="group_id", type=ArgumentType.STRING)]
        )
        result = parser.parse("my-group")
        assert result["group_id"] == "my-group"

    def test_parse_multiple_positionals(self):
        """Test multiple positional arguments in order."""
        parser = CommandArgumentParser(
            [
                Argument(name="email", type=ArgumentType.EMAIL),
                Argument(name="group_id", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse("user@example.com my-group")
        assert result["email"] == "user@example.com"
        assert result["group_id"] == "my-group"

    def test_parse_too_many_positionals(self):
        """Test error when too many positional arguments provided."""
        parser = CommandArgumentParser(
            [Argument(name="group_id", type=ArgumentType.STRING)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("my-group extra-arg")
        assert "Too many positional" in str(exc.value)

    def test_parse_positional_with_quoted_value(self):
        """Test positional argument with quoted value."""
        parser = CommandArgumentParser(
            [Argument(name="message", type=ArgumentType.STRING)]
        )
        result = parser.parse('"Hello world"')
        assert result["message"] == "Hello world"


class TestMixedParsing:
    """Test mixed positional and optional arguments."""

    def test_parse_positional_then_option(self):
        """Test positional argument followed by option."""
        parser = CommandArgumentParser(
            [
                Argument(name="group_id", type=ArgumentType.STRING),
                Argument(name="--role", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse("my-group --role OWNER")
        assert result["group_id"] == "my-group"
        assert result["--role"] == "OWNER"

    def test_parse_option_then_positional(self):
        """Test option before positional argument."""
        parser = CommandArgumentParser(
            [
                Argument(name="--role", type=ArgumentType.STRING),
                Argument(name="group_id", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse("--role OWNER my-group")
        assert result["--role"] == "OWNER"
        assert result["group_id"] == "my-group"

    def test_parse_complex_command(self):
        """Test complex command with mixed arguments."""
        parser = CommandArgumentParser(
            [
                Argument(name="action", type=ArgumentType.STRING),
                Argument(name="target", type=ArgumentType.STRING),
                Argument(name="--managed", type=ArgumentType.BOOLEAN),
                Argument(name="--role", type=ArgumentType.STRING),
                Argument(name="--justification", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse(
            'add user@example.com --managed --role OWNER --justification "Emergency access"'
        )
        assert result["action"] == "add"
        assert result["target"] == "user@example.com"
        assert result["--managed"] is True
        assert result["--role"] == "OWNER"
        assert result["--justification"] == "Emergency access"


class TestTypeValidation:
    """Test argument type validation."""

    def test_validate_email_valid(self):
        """Test valid email validation."""
        parser = CommandArgumentParser(
            [Argument(name="email", type=ArgumentType.EMAIL)]
        )
        result = parser.parse("user@example.com")
        assert result["email"] == "user@example.com"

    def test_validate_email_invalid(self):
        """Test invalid email raises error."""
        parser = CommandArgumentParser(
            [Argument(name="email", type=ArgumentType.EMAIL)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("not-an-email")
        assert "Invalid email" in str(exc.value)

    def test_validate_integer_valid(self):
        """Test valid integer validation."""
        parser = CommandArgumentParser(
            [Argument(name="count", type=ArgumentType.INTEGER)]
        )
        result = parser.parse("42")
        assert result["count"] == 42

    def test_validate_integer_invalid(self):
        """Test invalid integer raises error."""
        parser = CommandArgumentParser(
            [Argument(name="count", type=ArgumentType.INTEGER)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("not-a-number")
        assert "integer" in str(exc.value).lower()

    def test_validate_choice_valid(self):
        """Test valid choice validation."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="provider",
                    type=ArgumentType.CHOICE,
                    choices=["aws", "google", "azure"],
                )
            ]
        )
        result = parser.parse("aws")
        assert result["provider"] == "aws"

    def test_validate_choice_invalid(self):
        """Test invalid choice raises error."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="provider",
                    type=ArgumentType.CHOICE,
                    choices=["aws", "google", "azure"],
                )
            ]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("invalid")
        assert "Invalid choice" in str(exc.value)

    def test_validate_csv_multiple_values(self):
        """Test CSV parsing of comma-separated values."""
        parser = CommandArgumentParser(
            [Argument(name="--roles", type=ArgumentType.CSV)]
        )
        result = parser.parse("--roles OWNER,MEMBER,VIEWER")
        assert result["--roles"] == ["OWNER", "MEMBER", "VIEWER"]

    def test_validate_csv_strips_whitespace(self):
        """Test CSV parsing strips whitespace."""
        parser = CommandArgumentParser(
            [Argument(name="--roles", type=ArgumentType.CSV)]
        )
        result = parser.parse('--roles "OWNER , MEMBER , VIEWER"')
        assert result["--roles"] == ["OWNER", "MEMBER", "VIEWER"]


class TestRequiredValidation:
    """Test required argument validation."""

    def test_required_positional_present(self):
        """Test required positional argument is present."""
        parser = CommandArgumentParser(
            [Argument(name="group_id", type=ArgumentType.STRING, required=True)]
        )
        result = parser.parse("my-group")
        assert result["group_id"] == "my-group"

    def test_required_positional_missing(self):
        """Test error when required positional argument missing."""
        parser = CommandArgumentParser(
            [Argument(name="group_id", type=ArgumentType.STRING, required=True)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("")
        assert "required" in str(exc.value).lower() or "group_id" in str(exc.value)

    def test_required_option_present(self):
        """Test required option is present."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING, required=True)]
        )
        result = parser.parse("--role OWNER")
        assert result["--role"] == "OWNER"

    def test_required_option_missing(self):
        """Test error when required option missing."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING, required=True)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("")
        assert "--role" in str(exc.value)

    def test_multiple_required_arguments(self):
        """Test multiple required arguments."""
        parser = CommandArgumentParser(
            [
                Argument(name="email", type=ArgumentType.EMAIL, required=True),
                Argument(name="group_id", type=ArgumentType.STRING, required=True),
            ]
        )
        result = parser.parse("user@example.com my-group")
        assert result["email"] == "user@example.com"
        assert result["group_id"] == "my-group"

    def test_multiple_required_one_missing(self):
        """Test error when one required argument missing."""
        parser = CommandArgumentParser(
            [
                Argument(name="email", type=ArgumentType.EMAIL, required=True),
                Argument(name="group_id", type=ArgumentType.STRING, required=True),
            ]
        )
        with pytest.raises(ArgumentParsingError):
            parser.parse("user@example.com")


class TestDefaults:
    """Test default value handling."""

    def test_default_applied_when_missing(self):
        """Test default value applied when argument not provided."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING, default="MEMBER")]
        )
        result = parser.parse("")
        assert result.get("--role") == "MEMBER"

    def test_default_not_applied_when_provided(self):
        """Test default value not applied when argument provided."""
        parser = CommandArgumentParser(
            [Argument(name="--role", type=ArgumentType.STRING, default="MEMBER")]
        )
        result = parser.parse("--role OWNER")
        assert result["--role"] == "OWNER"

    def test_multiple_defaults(self):
        """Test multiple default values."""
        parser = CommandArgumentParser(
            [
                Argument(name="group_id", type=ArgumentType.STRING, required=True),
                Argument(
                    name="--role",
                    type=ArgumentType.STRING,
                    default="MEMBER",
                ),
                Argument(
                    name="--status",
                    type=ArgumentType.STRING,
                    default="active",
                ),
            ]
        )
        result = parser.parse("my-group")
        assert result["group_id"] == "my-group"
        assert result["--role"] == "MEMBER"
        assert result["--status"] == "active"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_input(self):
        """Test parsing empty input."""
        parser = CommandArgumentParser([])
        result = parser.parse("")
        assert result == {}

    def test_unknown_option(self):
        """Test error on unknown option."""
        parser = CommandArgumentParser(
            [Argument(name="--known", type=ArgumentType.STRING)]
        )
        with pytest.raises(ArgumentParsingError) as exc:
            parser.parse("--unknown value")
        assert "Unknown option" in str(exc.value)

    def test_whitespace_only_input(self):
        """Test parsing whitespace-only input."""
        parser = CommandArgumentParser([])
        result = parser.parse("   \t  \n  ")
        assert result == {}

    def test_option_value_looks_like_option(self):
        """Test option value that looks like an option name."""
        parser = CommandArgumentParser(
            [Argument(name="--pattern", type=ArgumentType.STRING)]
        )
        result = parser.parse('--pattern "--help"')
        assert result["--pattern"] == "--help"

    def test_single_dash_argument(self):
        """Test single-dash argument (like -r)."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="--role",
                    type=ArgumentType.STRING,
                    aliases=["-r"],
                )
            ]
        )
        result = parser.parse("-r OWNER")
        assert result["--role"] == "OWNER"
