"""Unit tests for groups command registry."""

import pytest
from infrastructure.commands.models import ArgumentType, Argument
from modules.groups.commands.registry import registry


class TestGroupsRegistry:
    """Tests for groups command registry."""

    def test_registry_namespace(self):
        """Test registry has correct namespace."""
        assert registry.namespace == "groups"

    def test_list_command_registered(self):
        """Test list command is registered."""
        cmd = registry.get_command("list")
        assert cmd is not None
        assert cmd.name == "list"

    def test_add_command_registered(self):
        """Test add command is registered."""
        cmd = registry.get_command("add")
        assert cmd is not None
        assert cmd.name == "add"

    def test_remove_command_registered(self):
        """Test remove command is registered."""
        cmd = registry.get_command("remove")
        assert cmd is not None
        assert cmd.name == "remove"

    def test_manage_command_registered(self):
        """Test manage command is registered."""
        cmd = registry.get_command("manage")
        assert cmd is not None
        assert cmd.name == "manage"

    def test_help_command_registered(self):
        """Test help command is registered."""
        cmd = registry.get_command("help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_list_command_arguments(self):
        """Test list command has correct arguments."""
        cmd = registry.get_command("list")
        assert len(cmd.args) > 0

        # Check provider argument
        provider_arg = next((a for a in cmd.args if a.name == "provider"), None)
        assert provider_arg is not None
        assert provider_arg.type == ArgumentType.STRING
        assert provider_arg.required is False
        assert provider_arg.choices == ["aws", "google", "azure"]

        # Check --user flag
        user_arg = next((a for a in cmd.args if a.name == "--user"), None)
        assert user_arg is not None
        assert user_arg.type == ArgumentType.EMAIL
        assert user_arg.flag is True
        assert user_arg.required is False

    def test_add_command_arguments(self):
        """Test add command has correct arguments."""
        cmd = registry.get_command("add")
        assert len(cmd.args) >= 3

        # Required positional arguments
        required_args = [a for a in cmd.args if a.required and not a.flag]
        assert len(required_args) >= 3

        # Check email argument
        email_arg = next((a for a in cmd.args if a.name == "member_email"), None)
        assert email_arg is not None
        assert email_arg.type == ArgumentType.EMAIL
        assert email_arg.required is True

        # Check group_id argument
        group_arg = next((a for a in cmd.args if a.name == "group_id"), None)
        assert group_arg is not None
        assert group_arg.type == ArgumentType.STRING
        assert group_arg.required is True

        # Check provider argument
        provider_arg = next((a for a in cmd.args if a.name == "provider"), None)
        assert provider_arg is not None
        assert provider_arg.required is True
        assert provider_arg.choices == ["aws", "google", "azure"]

    def test_remove_command_arguments(self):
        """Test remove command has correct arguments."""
        cmd = registry.get_command("remove")
        assert len(cmd.args) >= 3

        # Required positional arguments
        required_args = [a for a in cmd.args if a.required and not a.flag]
        assert len(required_args) >= 3

    def test_manage_command_arguments(self):
        """Test manage command has correct arguments."""
        cmd = registry.get_command("manage")
        # Optional provider filter
        provider_arg = next((a for a in cmd.args if a.name == "provider"), None)
        assert provider_arg is not None
        assert provider_arg.required is False

    def test_list_commands(self):
        """Test listing all commands."""
        commands = registry.list_commands()
        assert len(commands) >= 5
        command_names = {cmd.name for cmd in commands}
        assert "list" in command_names
        assert "add" in command_names
        assert "remove" in command_names
        assert "manage" in command_names
        assert "help" in command_names

    def test_find_command(self):
        """Test finding commands by name."""
        cmd = registry.find_command(["list"])
        assert cmd is not None
        assert cmd.name == "list"

    def test_command_has_handler(self):
        """Test all commands have handlers."""
        for cmd in registry.list_commands():
            assert cmd.handler is not None
            assert callable(cmd.handler)

    def test_command_description_keys(self):
        """Test commands have description keys for i18n."""
        list_cmd = registry.get_command("list")
        assert list_cmd.description_key is not None
        assert "groups" in list_cmd.description_key

        add_cmd = registry.get_command("add")
        assert add_cmd.description_key is not None
        assert "groups" in add_cmd.description_key

    def test_flag_arguments_validation(self):
        """Test flag arguments are properly configured."""
        list_cmd = registry.get_command("list")
        flags = [a for a in list_cmd.args if a.flag]

        for flag in flags:
            # All flags should start with --
            assert flag.name.startswith("--")
            # Flags should not be required
            assert flag.required is False
