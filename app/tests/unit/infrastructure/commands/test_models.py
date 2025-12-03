"""Unit tests for command framework models."""

import pytest
from infrastructure.commands.models import ArgumentType, ParsedCommand


class TestArgumentType:
    """Tests for ArgumentType enum."""

    def test_argument_type_has_all_types(self):
        """ArgumentType enum has expected values."""
        types = [e.value for e in ArgumentType]
        assert "string" in types
        assert "integer" in types
        assert "boolean" in types
        assert "float" in types
        assert "email" in types


class TestArgument:
    """Tests for Argument model."""

    def test_argument_creation_with_defaults(self, argument_factory):
        """Argument can be created with minimal parameters."""
        arg = argument_factory()
        assert arg.name == "arg"
        assert arg.type == ArgumentType.STRING
        assert arg.required is True
        assert arg.flag is False
        assert arg.default is None

    def test_argument_creation_with_custom_values(self, argument_factory):
        """Argument can be created with custom values."""
        arg = argument_factory(
            name="email",
            arg_type=ArgumentType.EMAIL,
            required=False,
            default="test@example.com",
            description="User email",
        )
        assert arg.name == "email"
        assert arg.type == ArgumentType.EMAIL
        assert arg.required is False
        assert arg.default == "test@example.com"
        assert arg.description == "User email"

    def test_flag_argument_creation(self, argument_factory):
        """Flag arguments can be created with --prefix."""
        arg = argument_factory(
            name="--verbose",
            arg_type=ArgumentType.BOOLEAN,
            flag=True,
            required=False,
        )
        assert arg.name == "--verbose"
        assert arg.flag is True
        assert arg.required is False

    def test_flag_argument_requires_double_dash(self, argument_factory):
        """Flag arguments must start with --."""
        with pytest.raises(ValueError, match="Flag arguments must start with"):
            argument_factory(name="-v", flag=True)

    def test_flag_argument_cannot_be_required(self, argument_factory):
        """Flag arguments cannot be required."""
        with pytest.raises(ValueError, match="Flag arguments cannot be required"):
            argument_factory(name="--verbose", flag=True, required=True)

    def test_argument_with_choices(self, argument_factory):
        """Argument can have restricted choices."""
        arg = argument_factory(
            name="color",
            choices=["red", "green", "blue"],
        )
        assert arg.choices == ["red", "green", "blue"]


class TestCommand:
    """Tests for Command model."""

    def test_command_creation_with_defaults(self, command_factory):
        """Command can be created with minimal parameters."""
        cmd = command_factory()
        assert cmd.name == "test"
        assert cmd.handler is not None
        assert cmd.description == ""
        assert cmd.args == []
        assert cmd.subcommands == {}

    def test_command_creation_with_arguments(self, command_factory, argument_factory):
        """Command can have arguments."""
        args = [
            argument_factory(name="email"),
            argument_factory(name="--force", flag=True, required=False),
        ]
        cmd = command_factory(name="add", args=args, description="Add member")
        assert cmd.name == "add"
        assert len(cmd.args) == 2
        assert cmd.description == "Add member"

    def test_get_required_args(self, command_factory, argument_factory):
        """get_required_args returns only required positional arguments."""
        args = [
            argument_factory(name="email", required=True),
            argument_factory(name="group", required=True),
            argument_factory(name="--force", flag=True, required=False),
            argument_factory(name="reason", required=False),
        ]
        cmd = command_factory(args=args)
        required = cmd.get_required_args()

        assert len(required) == 2
        assert all(arg.name in ("email", "group") for arg in required)

    def test_get_optional_args(self, command_factory, argument_factory):
        """get_optional_args returns only optional positional arguments."""
        args = [
            argument_factory(name="email", required=True),
            argument_factory(name="reason", required=False),
            argument_factory(name="--force", flag=True, required=False),
        ]
        cmd = command_factory(args=args)
        optional = cmd.get_optional_args()

        assert len(optional) == 1
        assert optional[0].name == "reason"

    def test_get_flags(self, command_factory, argument_factory):
        """get_flags returns only flag arguments."""
        args = [
            argument_factory(name="email", required=True),
            argument_factory(name="--verbose", flag=True, required=False),
            argument_factory(name="--force", flag=True, required=False),
        ]
        cmd = command_factory(args=args)
        flags = cmd.get_flags()

        assert len(flags) == 2
        assert all(arg.flag for arg in flags)

    def test_add_subcommand(self, command_factory):
        """Subcommands can be added to commands."""
        parent = command_factory(name="list")
        child = command_factory(name="managed")

        parent.add_subcommand(child)

        assert "managed" in parent.subcommands
        assert parent.subcommands["managed"] == child

    def test_subcommand_access(self, command_factory):
        """Subcommands are accessible by name."""
        parent = command_factory(name="list")
        child1 = command_factory(name="active")
        child2 = command_factory(name="archived")

        parent.add_subcommand(child1)
        parent.add_subcommand(child2)

        assert len(parent.subcommands) == 2
        assert parent.subcommands["active"].name == "active"
        assert parent.subcommands["archived"].name == "archived"


class TestParsedCommand:
    """Tests for ParsedCommand model."""

    def test_parsed_command_creation(self, command_factory):
        """ParsedCommand captures parse results."""
        cmd = command_factory(name="list")
        args = {"provider": "google", "managed": True}
        parsed = ParsedCommand(command=cmd, args=args, raw_text="list google --managed")

        assert parsed.command == cmd
        assert parsed.args == args
        assert parsed.raw_text == "list google --managed"
        assert parsed.subcommand is None

    def test_parsed_command_with_subcommand(self, command_factory):
        """ParsedCommand can reference a nested subcommand."""
        parent = command_factory(name="list")
        child = command_factory(name="managed")

        parsed_child = ParsedCommand(command=child, args={}, raw_text="managed")
        parsed_parent = ParsedCommand(
            command=parent, args={}, raw_text="list managed", subcommand=parsed_child
        )

        assert parsed_parent.subcommand == parsed_child
        assert parsed_parent.subcommand.command.name == "managed"
