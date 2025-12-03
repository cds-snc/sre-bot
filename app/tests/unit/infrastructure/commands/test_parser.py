"""Unit tests for CommandParser."""

import pytest
from infrastructure.commands.models import ArgumentType
from infrastructure.commands.parser import CommandParseError


class TestCommandParserPositional:
    """Tests for parsing positional arguments."""

    def test_parse_single_positional_argument(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles single positional argument."""
        args = [argument_factory(name="email", arg_type=ArgumentType.EMAIL)]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["alice@example.com"])

        assert result.args["email"] == "alice@example.com"

    def test_parse_multiple_positional_arguments(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles multiple positional arguments."""
        args = [
            argument_factory(name="name", arg_type=ArgumentType.STRING),
            argument_factory(name="email", arg_type=ArgumentType.EMAIL),
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["alice", "alice@example.com"])

        assert result.args["name"] == "alice"
        assert result.args["email"] == "alice@example.com"

    def test_parse_optional_positional_argument(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles optional positional arguments."""
        args = [
            argument_factory(name="group", arg_type=ArgumentType.STRING, required=True),
            argument_factory(
                name="reason", arg_type=ArgumentType.STRING, required=False
            ),
        ]
        cmd = command_factory(args=args)

        # With optional arg provided
        result = command_parser.parse(cmd, ["group-1", "testing"])
        assert result.args["group"] == "group-1"
        assert result.args["reason"] == "testing"

        # Without optional arg
        result = command_parser.parse(cmd, ["group-1"])
        assert result.args["group"] == "group-1"
        assert "reason" not in result.args

    def test_parse_missing_required_argument_raises(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser raises if required argument missing."""
        args = [argument_factory(name="email", required=True)]
        cmd = command_factory(args=args)

        with pytest.raises(CommandParseError, match="Missing required argument"):
            command_parser.parse(cmd, [])

    def test_parse_extra_positional_arguments_raises(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser raises if extra positional arguments provided."""
        args = [argument_factory(name="email")]
        cmd = command_factory(args=args)

        with pytest.raises(CommandParseError, match="Extra arguments"):
            command_parser.parse(cmd, ["alice@example.com", "extra"])


class TestCommandParserQuotedStrings:
    """Tests for quoted string handling."""

    def test_parse_quoted_string_double_quotes(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles double-quoted strings."""
        args = [argument_factory(name="text")]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ['"hello world"'])

        assert result.args["text"] == "hello world"

    def test_parse_quoted_string_single_quotes(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles single-quoted strings."""
        args = [argument_factory(name="text")]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["'hello world'"])

        assert result.args["text"] == "hello world"

    def test_parse_multi_token_quoted_string(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles multi-token quoted strings."""
        args = [argument_factory(name="reason")]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ['"testing', "the", 'parser"'])

        assert result.args["reason"] == "testing the parser"


class TestCommandParserFlags:
    """Tests for flag argument handling."""

    def test_parse_flag_with_value(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles flag with value (--key=value)."""
        args = [
            argument_factory(
                name="--force", flag=True, arg_type=ArgumentType.BOOLEAN, required=False
            )
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["--force=true"])

        assert result.args["--force"] is True

    def test_parse_flag_without_value_defaults_true(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser assumes flag is true if no value provided."""
        args = [
            argument_factory(
                name="--verbose",
                flag=True,
                arg_type=ArgumentType.BOOLEAN,
                required=False,
            )
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["--verbose"])

        assert result.args["--verbose"] is True

    def test_parse_missing_optional_flag(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles missing optional flags."""
        args = [
            argument_factory(
                name="--force", flag=True, arg_type=ArgumentType.BOOLEAN, required=False
            )
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, [])

        assert "--force" not in result.args

    def test_parse_flag_with_string_value(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles flag with string value."""
        args = [
            argument_factory(
                name="--provider",
                flag=True,
                arg_type=ArgumentType.STRING,
                required=False,
            )
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["--provider=google"])

        assert result.args["--provider"] == "google"


class TestCommandParserTypeCoercion:
    """Tests for type coercion."""

    def test_coerce_integer(self, command_parser, command_factory, argument_factory):
        """Parser coerces string to integer."""
        args = [argument_factory(name="count", arg_type=ArgumentType.INTEGER)]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["42"])

        assert result.args["count"] == 42
        assert isinstance(result.args["count"], int)

    def test_coerce_float(self, command_parser, command_factory, argument_factory):
        """Parser coerces string to float."""
        args = [argument_factory(name="ratio", arg_type=ArgumentType.FLOAT)]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["3.14"])

        assert result.args["ratio"] == 3.14
        assert isinstance(result.args["ratio"], float)

    def test_coerce_boolean_true(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser coerces string to boolean true."""
        args = [argument_factory(name="enabled", arg_type=ArgumentType.BOOLEAN)]
        cmd = command_factory(args=args)

        for value in ["true", "1", "yes", "on"]:
            result = command_parser.parse(cmd, [value])
            assert result.args["enabled"] is True

    def test_coerce_boolean_false(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser coerces string to boolean false."""
        args = [argument_factory(name="enabled", arg_type=ArgumentType.BOOLEAN)]
        cmd = command_factory(args=args)

        for value in ["false", "0", "no", "off"]:
            result = command_parser.parse(cmd, [value])
            assert result.args["enabled"] is False

    def test_coerce_invalid_integer_raises(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser raises on invalid integer."""
        args = [argument_factory(name="count", arg_type=ArgumentType.INTEGER)]
        cmd = command_factory(args=args)

        with pytest.raises(CommandParseError, match="Cannot convert"):
            command_parser.parse(cmd, ["not-a-number"])

    def test_coerce_invalid_email_raises(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser raises on invalid email."""
        args = [argument_factory(name="email", arg_type=ArgumentType.EMAIL)]
        cmd = command_factory(args=args)

        with pytest.raises(CommandParseError, match="Invalid email"):
            command_parser.parse(cmd, ["not-an-email"])


class TestCommandParserValidation:
    """Tests for validation."""

    def test_validate_choices(self, command_parser, command_factory, argument_factory):
        """Parser validates argument choices."""
        args = [
            argument_factory(
                name="color",
                arg_type=ArgumentType.STRING,
                choices=["red", "green", "blue"],
            )
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["red"])
        assert result.args["color"] == "red"

    def test_validate_invalid_choice_raises(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser raises on invalid choice."""
        args = [
            argument_factory(
                name="color",
                arg_type=ArgumentType.STRING,
                choices=["red", "green", "blue"],
            )
        ]
        cmd = command_factory(args=args)

        with pytest.raises(CommandParseError, match="Invalid value"):
            command_parser.parse(cmd, ["yellow"])

    def test_parse_raw_text_preserved(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser preserves raw command text."""
        args = [
            argument_factory(name="arg1"),
            argument_factory(name="arg2"),
        ]
        cmd = command_factory(args=args)
        tokens = ["value1", "value2"]

        result = command_parser.parse(cmd, tokens)

        assert result.raw_text == "value1 value2"


class TestCommandParserComplexScenarios:
    """Tests for complex parsing scenarios."""

    def test_parse_positional_with_flags(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles positional arguments mixed with flags."""
        args = [
            argument_factory(name="email"),
            argument_factory(name="group"),
            argument_factory(
                name="--force", flag=True, arg_type=ArgumentType.BOOLEAN, required=False
            ),
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ["alice@example.com", "group-1", "--force"])

        assert result.args["email"] == "alice@example.com"
        assert result.args["group"] == "group-1"
        assert result.args["--force"] is True

    def test_parse_quoted_positional_with_flags(
        self, command_parser, command_factory, argument_factory
    ):
        """Parser handles quoted positionals with flags."""
        args = [
            argument_factory(name="reason"),
            argument_factory(
                name="--urgent",
                flag=True,
                arg_type=ArgumentType.BOOLEAN,
                required=False,
            ),
        ]
        cmd = command_factory(args=args)

        result = command_parser.parse(cmd, ['"testing and validation"', "--urgent"])

        assert result.args["reason"] == "testing and validation"
        assert result.args["--urgent"] is True
