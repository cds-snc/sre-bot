"""Unit tests for SlackCommandAdapter."""

from unittest.mock import MagicMock

from infrastructure.commands.adapters import SlackCommandAdapter
from infrastructure.commands.models import Argument, ArgumentType


class TestSlackCommandAdapterInitialization:
    """Tests for adapter initialization."""

    def test_adapter_initialization(self, command_registry_factory):
        """Adapter initializes with registry."""
        registry = command_registry_factory(namespace="groups")
        adapter = SlackCommandAdapter(registry)

        assert adapter.registry == registry
        assert adapter.translator is None

    def test_adapter_with_translator(self, command_registry_factory, mock_translator):
        """Adapter accepts translator."""
        registry = command_registry_factory()
        adapter = SlackCommandAdapter(registry, translator=mock_translator)

        assert adapter.translator == mock_translator


class TestSlackCommandAdapterTokenization:
    """Tests for command tokenization."""

    def test_tokenize_simple_command(self, command_registry_factory):
        """Adapter tokenizes simple command."""
        adapter = SlackCommandAdapter(command_registry_factory())

        tokens = adapter._tokenize("list")  # pylint: disable=protected-access

        assert tokens == ["list"]

    def test_tokenize_command_with_args(self, command_registry_factory):
        """Adapter tokenizes command with arguments."""
        adapter = SlackCommandAdapter(command_registry_factory())

        tokens = adapter._tokenize(
            "add alice@example.com group-1"
        )  # pylint: disable=protected-access

        assert tokens == ["add", "alice@example.com", "group-1"]

    def test_tokenize_quoted_string(self, command_registry_factory):
        """Adapter handles quoted strings."""
        adapter = SlackCommandAdapter(command_registry_factory())

        tokens = adapter._tokenize(
            '"hello world" testing'
        )  # pylint: disable=protected-access

        assert tokens == ["hello world", "testing"]

    def test_tokenize_multiple_spaces(self, command_registry_factory):
        """Adapter handles multiple spaces."""
        adapter = SlackCommandAdapter(command_registry_factory())

        tokens = adapter._tokenize("list    active")  # pylint: disable=protected-access

        assert tokens == ["list", "active"]


class TestSlackCommandAdapterHandling:
    """Tests for command handling."""

    def test_handle_acknowledges_immediately(
        self,
        command_registry_factory,
        mock_slack_ack,
        mock_slack_respond,
        mock_slack_client,
        slack_command_payload,
    ):
        """Handler acknowledges command immediately."""
        adapter = SlackCommandAdapter(command_registry_factory())

        adapter.handle(
            mock_slack_ack, slack_command_payload, mock_slack_client, mock_slack_respond
        )

        mock_slack_ack.assert_called_once()

    def test_handle_help_command(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
    ):
        """Handler provides help when requested."""
        registry = command_registry_factory(namespace="groups")

        @registry.command(name="list", description="List groups")
        def list_groups(ctx):  # pylint: disable=unused-argument
            pass

        adapter = SlackCommandAdapter(registry)
        payload = {
            "command": "/sre",
            "text": "help",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        mock_slack_respond.assert_called()
        help_text = mock_slack_respond.call_args[1]["text"]
        assert "*GROUPS COMMANDS*" in help_text.upper()
        assert "list" in help_text

    def test_handle_unknown_command(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
    ):
        """Handler responds with error for unknown command."""
        registry = command_registry_factory()
        adapter = SlackCommandAdapter(registry)
        payload = {
            "command": "/sre",
            "text": "unknown",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        mock_slack_respond.assert_called()
        response = mock_slack_respond.call_args[1]["text"]
        assert "Unknown command" in response

    def test_handle_calls_command_handler(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
    ):
        """Handler calls registered command."""
        registry = command_registry_factory()
        handler_called = []

        @registry.command(name="test")
        def test_cmd(ctx):  # pylint: disable=unused-argument
            handler_called.append(True)

        adapter = SlackCommandAdapter(registry)
        payload = {
            "command": "/sre",
            "text": "test",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        assert len(handler_called) == 1

    def test_handle_parse_error(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
    ):
        """Handler responds with error on parse failure."""
        registry = command_registry_factory()

        @registry.command(
            name="add", args=[Argument("email", type=ArgumentType.EMAIL, required=True)]
        )
        def add_cmd(ctx, email):  # pylint: disable=unused-argument
            pass

        adapter = SlackCommandAdapter(registry)
        payload = {
            "command": "/sre",
            "text": "add invalid-email",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        mock_slack_respond.assert_called()
        response = mock_slack_respond.call_args[1]["text"]
        assert "Invalid email" in response or "error" in response.lower()

    def test_handle_passes_context_to_handler(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
    ):
        """Handler passes CommandContext to registered handler."""
        registry = command_registry_factory()
        captured_context = []

        @registry.command(name="test")
        def test_cmd(ctx):  # pylint: disable=unused-argument
            captured_context.append(ctx)

        adapter = SlackCommandAdapter(registry)
        payload = {
            "command": "/sre",
            "text": "test",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        assert len(captured_context) == 1
        ctx = captured_context[0]
        assert ctx.platform == "slack"
        assert ctx.user_id == "U123"
        assert ctx.channel_id == "C123"

    def test_handle_injects_translator(
        self,
        command_registry_factory,
        mock_slack_respond,
        mock_slack_client,
        mock_slack_ack,
        mock_translator,
    ):
        """Handler injects translator into context."""
        registry = command_registry_factory()
        captured_context = []

        @registry.command(name="test")
        def test_cmd(ctx):  # pylint: disable=unused-argument
            captured_context.append(ctx)

        adapter = SlackCommandAdapter(registry, translator=mock_translator)
        payload = {
            "command": "/sre",
            "text": "test",
            "user_id": "U123",
            "channel_id": "C123",
        }

        adapter.handle(mock_slack_ack, payload, mock_slack_client, mock_slack_respond)

        ctx = captured_context[0]
        assert ctx._translator == mock_translator  # pylint: disable=protected-access


class TestSlackResponseChannel:
    """Tests for SlackResponseChannel."""

    def test_send_message(self, mock_slack_respond):
        """SlackResponseChannel sends message via respond."""
        from infrastructure.commands.adapters import SlackResponseChannel

        channel = SlackResponseChannel(mock_slack_respond, MagicMock(), "C123", "U123")

        channel.send_message("Hello")

        mock_slack_respond.assert_called_once_with(text="Hello")

    def test_send_ephemeral(self, mock_slack_client):
        """SlackResponseChannel sends ephemeral via client."""
        from infrastructure.commands.adapters import SlackResponseChannel

        respond_mock = MagicMock()
        channel = SlackResponseChannel(respond_mock, mock_slack_client, "C123", "U123")

        channel.send_ephemeral("Secret message")

        mock_slack_client.chat_postEphemeral.assert_called_once_with(
            channel="C123", user="U123", text="Secret message"
        )


class TestSlackCommandAdapterHelpGeneration:
    """Tests for help text generation."""

    def test_generate_help_includes_commands(self, command_registry_factory):
        """Help text includes all registered commands."""
        registry = command_registry_factory(namespace="groups")

        @registry.command(
            name="list",
            description="List all groups",
            examples=["list --active"],
        )
        def list_groups(ctx):  # pylint: disable=unused-argument
            pass

        adapter = SlackCommandAdapter(registry)
        help_text = adapter._generate_help()  # pylint: disable=protected-access

        assert "list" in help_text
        assert "List all groups" in help_text
        assert "list --active" in help_text

    def test_generate_help_includes_arguments(self, command_registry_factory):
        """Help text includes command arguments."""
        registry = command_registry_factory(namespace="groups")

        @registry.command(
            name="add",
            args=[
                Argument("email", type=ArgumentType.EMAIL, description="Member email"),
                Argument(
                    "--force",
                    flag=True,
                    type=ArgumentType.BOOLEAN,
                    required=False,
                    description="Skip confirmation",
                ),
            ],
        )
        def add_member(ctx, email, force=False):  # pylint: disable=unused-argument
            pass

        adapter = SlackCommandAdapter(registry)
        help_text = adapter._generate_help()  # pylint: disable=protected-access

        assert "email" in help_text
        assert "Member email" in help_text
        assert "--force" in help_text
        assert "Skip confirmation" in help_text

    def test_generate_help_includes_subcommands(self, command_registry_factory):
        """Help text includes subcommands."""
        registry = command_registry_factory(namespace="groups")

        @registry.command(name="list")
        def list_groups(ctx):  # pylint: disable=unused-argument
            pass

        @registry.subcommand("list", name="active", description="List active groups")
        def list_active(ctx):  # pylint: disable=unused-argument
            pass

        adapter = SlackCommandAdapter(registry)
        help_text = adapter._generate_help()  # pylint: disable=protected-access

        assert "Subcommands" in help_text
        assert "active" in help_text
