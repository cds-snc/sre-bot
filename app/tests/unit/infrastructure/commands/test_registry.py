"""Unit tests for CommandRegistry."""

import pytest
from infrastructure.commands.models import Argument, ArgumentType


class TestCommandRegistry:
    """Tests for CommandRegistry registration and discovery."""

    def test_registry_initialization(self, command_registry_factory):
        """Registry initializes with namespace."""
        registry = command_registry_factory(namespace="groups")
        assert registry.namespace == "groups"
        assert registry.list_commands() == []

    def test_command_registration_via_decorator(self, command_registry_factory):
        """Commands can be registered using decorator."""
        registry = command_registry_factory()

        @registry.command(name="list", description="List items")
        def list_items(ctx):
            pass

        cmd = registry.get_command("list")
        assert cmd is not None
        assert cmd.name == "list"
        assert cmd.description == "List items"
        assert cmd.handler == list_items

    def test_get_command_returns_none_for_missing(self, command_registry_factory):
        """get_command returns None if command not found."""
        registry = command_registry_factory()

        cmd = registry.get_command("nonexistent")
        assert cmd is None

    def test_list_commands_returns_all_commands(self, command_registry_factory):
        """list_commands returns all registered commands."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_items(ctx):
            pass

        @registry.command(name="add")
        def add_item(ctx):
            pass

        commands = registry.list_commands()
        assert len(commands) == 2
        assert any(cmd.name == "list" for cmd in commands)
        assert any(cmd.name == "add" for cmd in commands)

    def test_command_with_arguments(self, command_registry_factory):
        """Commands can be registered with arguments."""
        registry = command_registry_factory()

        args = [
            Argument("email", type=ArgumentType.EMAIL),
            Argument("--force", type=ArgumentType.BOOLEAN, flag=True, required=False),
        ]

        @registry.command(name="add", args=args)
        def add_member(ctx, email: str, force: bool = False):
            pass

        cmd = registry.get_command("add")
        assert len(cmd.args) == 2
        assert cmd.args[0].name == "email"
        assert cmd.args[1].name == "--force"

    def test_subcommand_registration(self, command_registry_factory):
        """Subcommands can be registered."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_cmd(ctx):
            pass

        @registry.subcommand("list", name="active")
        def list_active(ctx):
            pass

        parent_cmd = registry.get_command("list")
        assert "active" in parent_cmd.subcommands
        assert parent_cmd.subcommands["active"].name == "active"

    def test_subcommand_requires_parent(self, command_registry_factory):
        """Subcommand registration fails if parent doesn't exist."""
        registry = command_registry_factory()

        with pytest.raises(ValueError, match="Parent command .* not found"):

            @registry.subcommand("nonexistent", name="child")
            def child_cmd(ctx):
                pass

            # Decorator is applied during definition above
            pass

    def test_multiple_subcommands_on_same_parent(self, command_registry_factory):
        """Multiple subcommands can be added to same parent."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_cmd(ctx):
            pass

        @registry.subcommand("list", name="active")
        def list_active(ctx):
            pass

        @registry.subcommand("list", name="archived")
        def list_archived(ctx):
            pass

        parent = registry.get_command("list")
        assert len(parent.subcommands) == 2
        assert "active" in parent.subcommands
        assert "archived" in parent.subcommands

    def test_find_command_single_level(self, command_registry_factory):
        """find_command locates top-level commands."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_cmd(ctx):
            pass

        cmd = registry.find_command(["list"])
        assert cmd is not None
        assert cmd.name == "list"

    def test_find_command_nested(self, command_registry_factory):
        """find_command locates nested subcommands."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_cmd(ctx):
            pass

        @registry.subcommand("list", name="active")
        def list_active(ctx):
            pass

        cmd = registry.find_command(["list", "active"])
        assert cmd is not None
        assert cmd.name == "active"

    def test_find_command_returns_none_for_nonexistent(self, command_registry_factory):
        """find_command returns None for missing commands."""
        registry = command_registry_factory()

        cmd = registry.find_command(["nonexistent"])
        assert cmd is None

    def test_find_command_returns_none_for_empty_parts(self, command_registry_factory):
        """find_command returns None for empty parts."""
        registry = command_registry_factory()

        cmd = registry.find_command([])
        assert cmd is None

    def test_find_command_with_invalid_subcommand(self, command_registry_factory):
        """find_command returns None if intermediate subcommand doesn't exist."""
        registry = command_registry_factory()

        @registry.command(name="list")
        def list_cmd(ctx):
            pass

        cmd = registry.find_command(["list", "nonexistent"])
        assert cmd is None

    def test_command_with_examples(self, command_registry_factory):
        """Commands can have examples."""
        registry = command_registry_factory()

        @registry.command(
            name="add",
            examples=["user@example.com group-1", "admin@example.com group-1"],
        )
        def add_member(ctx):
            pass

        cmd = registry.get_command("add")
        assert len(cmd.examples) == 2
        assert "user@example.com group-1" in cmd.examples

    def test_command_with_translation_keys(self, command_registry_factory):
        """Commands can have translation keys."""
        registry = command_registry_factory()

        @registry.command(
            name="add",
            description_key="groups.commands.add.description",
            example_keys=["groups.examples.add.1", "groups.examples.add.2"],
        )
        def add_member(ctx):
            pass

        cmd = registry.get_command("add")
        assert cmd.description_key == "groups.commands.add.description"
        assert len(cmd.example_keys) == 2
