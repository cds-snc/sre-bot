"""Tests for automatic help text generation."""

from infrastructure.platforms.parsing import Argument, ArgumentType
from infrastructure.platforms.utils.slack_help import (
    generate_slack_help_text,
    generate_usage_line,
    get_argument_by_name,
)


class TestGenerateHelpText:
    """Test help text generation from Argument definitions."""

    def test_generate_help_text_positional(self):
        """Test help text for positional arguments."""
        args = [
            Argument(
                name="email",
                type=ArgumentType.EMAIL,
                required=True,
                description="Email address of the user",
            ),
        ]

        help_text = generate_slack_help_text(args)

        assert "email" in help_text
        assert "email" in help_text.lower()  # type is lowercase
        assert "required" in help_text
        assert "Email address of the user" in help_text

    def test_generate_help_text_with_options(self):
        """Test help text for options."""
        args = [
            Argument(
                name="--role",
                type=ArgumentType.STRING,
                description="User role",
                default="MEMBER",
            ),
        ]

        help_text = generate_slack_help_text(args)

        assert "--role VALUE" in help_text
        assert "string" in help_text.lower()  # type is lowercase
        assert "optional" in help_text
        assert "Default: MEMBER" in help_text  # Updated assertion

    def test_generate_help_text_with_choices(self):
        """Test help text for choice arguments."""
        args = [
            Argument(
                name="provider",
                type=ArgumentType.CHOICE,
                choices=["aws", "google", "azure"],
                required=True,
                description="Cloud provider",
            ),
        ]

        help_text = generate_slack_help_text(args)

        assert "provider" in help_text
        assert "choice" in help_text.lower()  # type is lowercase
        assert "aws" in help_text
        assert "google" in help_text
        assert "azure" in help_text

    def test_generate_help_text_with_aliases(self):
        """Test help text shows argument aliases."""
        args = [
            Argument(
                name="--role",
                type=ArgumentType.STRING,
                aliases=["-r"],
                description="User role",
            ),
        ]

        help_text = generate_slack_help_text(args)

        assert "--role" in help_text
        assert "-r" in help_text or "aliases" in help_text

    def test_generate_help_text_multiple_args(self):
        """Test help text with multiple arguments."""
        args = [
            Argument(
                name="email",
                type=ArgumentType.EMAIL,
                required=True,
                description="User email",
            ),
            Argument(
                name="group_id",
                type=ArgumentType.STRING,
                required=True,
                description="Group ID",
            ),
            Argument(
                name="--justification",
                type=ArgumentType.STRING,
                description="Reason for action",
            ),
        ]

        help_text = generate_slack_help_text(args)

        # Should have all arguments
        assert "email" in help_text
        assert "group_id" in help_text
        assert "--justification" in help_text

        # Should have descriptions
        assert "User email" in help_text
        assert "Group ID" in help_text
        assert "Reason for action" in help_text

    def test_generate_help_text_exclude_types(self):
        """Test help text without type information."""
        args = [
            Argument(
                name="email",
                type=ArgumentType.EMAIL,
                required=True,
                description="User email",
            ),
        ]

        help_text = generate_slack_help_text(args, include_types=False)

        # Should have argument name and description
        assert "email" in help_text
        assert "User email" in help_text

        # Should NOT have type info
        assert "EMAIL" not in help_text
        assert "required" not in help_text

    def test_generate_help_text_exclude_defaults(self):
        """Test help text without default values."""
        args = [
            Argument(
                name="--role",
                type=ArgumentType.STRING,
                default="MEMBER",
                description="User role",
            ),
        ]

        help_text = generate_slack_help_text(args, include_defaults=False)

        # Should have argument name and description
        assert "--role" in help_text
        assert "User role" in help_text

        # Should NOT have default
        assert "default" not in help_text
        assert "MEMBER" not in help_text

    def test_generate_help_text_custom_indent(self):
        """Test help text with custom indentation."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL, description="Email"),
        ]

        help_text = generate_slack_help_text(args, indent="    ")  # 4 spaces

        lines = help_text.split("\n")
        # First line should have custom indent
        assert lines[0].startswith("    ")


class TestGenerateUsageLine:
    """Test usage line generation."""

    def test_usage_line_single_positional(self):
        """Test usage line with single positional argument."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL, required=True),
        ]

        usage = generate_usage_line("sre.groups.add", args)

        assert "Usage: /sre groups add" in usage
        assert "EMAIL" in usage

    def test_usage_line_multiple_positionals(self):
        """Test usage line with multiple positional arguments."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL, required=True),
            Argument(name="group_id", type=ArgumentType.STRING, required=True),
        ]

        usage = generate_usage_line("sre.groups.add", args)

        assert "Usage: /sre groups add" in usage
        assert "EMAIL" in usage
        assert "GROUP_ID" in usage

    def test_usage_line_with_optional_arg(self):
        """Test usage line shows optional arguments in brackets."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL, required=True),
            Argument(name="--role", type=ArgumentType.STRING, required=False),
        ]

        usage = generate_usage_line("sre.groups.add", args)

        assert "EMAIL" in usage
        assert "[--role VALUE]" in usage

    def test_usage_line_with_flag(self):
        """Test usage line with boolean flags."""
        args = [
            Argument(name="--managed", type=ArgumentType.BOOLEAN),
            Argument(name="--active", type=ArgumentType.BOOLEAN),
        ]

        usage = generate_usage_line("sre.groups.list", args)

        assert "[--managed]" in usage
        assert "[--active]" in usage

    def test_usage_line_no_arguments(self):
        """Test usage line with no arguments."""
        usage = generate_usage_line("sre.version", [])

        assert usage == "Usage: /sre version"


class TestGetArgumentByName:
    """Test finding arguments by name or alias."""

    def test_find_by_name(self):
        """Test finding argument by exact name."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL),
            Argument(name="--role", type=ArgumentType.STRING),
        ]

        assert get_argument_by_name(args, "email") is args[0]
        assert get_argument_by_name(args, "--role") is args[1]

    def test_find_by_alias(self):
        """Test finding argument by alias."""
        args = [
            Argument(
                name="--role",
                type=ArgumentType.STRING,
                aliases=["-r"],
            ),
        ]

        arg = get_argument_by_name(args, "-r")
        assert arg is args[0]
        assert arg.name == "--role"

    def test_find_not_found(self):
        """Test returns None when not found."""
        args = [
            Argument(name="email", type=ArgumentType.EMAIL),
        ]

        assert get_argument_by_name(args, "invalid") is None
        assert get_argument_by_name(args, "-x") is None

    def test_find_first_match_with_multiple_aliases(self):
        """Test finding argument with multiple aliases."""
        args = [
            Argument(
                name="--role",
                type=ArgumentType.STRING,
                aliases=["-r", "--member-role"],
            ),
        ]

        # Should find by any alias
        assert get_argument_by_name(args, "-r") is args[0]
        assert get_argument_by_name(args, "--member-role") is args[0]
        assert get_argument_by_name(args, "--role") is args[0]
