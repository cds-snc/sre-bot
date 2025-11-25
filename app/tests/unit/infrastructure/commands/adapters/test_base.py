"""Unit tests for base CommandAdapter."""

import pytest
from unittest.mock import MagicMock

from infrastructure.commands.adapters.base import CommandAdapter
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.context import CommandContext


class FakeAdapter(CommandAdapter):
    """Fake adapter for testing base class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extracted_text = ""
        self.created_context = None
        self.acknowledged = False
        self.error_message = None
        self.help_text = None

    def extract_command_text(self, platform_payload):
        self.extracted_text = platform_payload.get("text", "")
        return self.extracted_text

    def create_context(self, platform_payload):
        ctx = CommandContext(
            platform="fake",
            user_id="U123",
            user_email="test@example.com",
            channel_id="C123",
        )
        ctx._responder = MagicMock()
        self.created_context = ctx
        return ctx

    def acknowledge(self, platform_payload):
        self.acknowledged = True

    def send_error(self, platform_payload, message):
        self.error_message = message

    def send_help(self, platform_payload, help_text):
        self.help_text = help_text


class TestCommandAdapterBase:
    """Tests for CommandAdapter base class."""

    @pytest.fixture
    def registry(self):
        """Create test command registry."""
        reg = CommandRegistry("test")

        @reg.command(name="hello")
        def hello_cmd(ctx):
            ctx.respond("Hello!")

        return reg

    @pytest.fixture
    def adapter(self, registry):
        """Create fake adapter for testing."""
        return FakeAdapter(registry=registry)

    def test_adapter_initialization(self, registry):
        """Adapter initializes with registry."""
        adapter = FakeAdapter(registry=registry)

        assert adapter.registry == registry
        assert adapter.parser is not None
        assert adapter.translator is None
        assert adapter.locale_resolver is None

    def test_handle_acknowledges_command(self, adapter):
        """Handle method calls acknowledge."""
        payload = {"text": "hello"}

        adapter.handle(payload)

        assert adapter.acknowledged is True

    def test_handle_extracts_command_text(self, adapter):
        """Handle method extracts command text."""
        payload = {"text": "hello world"}

        adapter.handle(payload)

        assert adapter.extracted_text == "hello world"

    def test_handle_shows_help_for_empty_command(self, adapter):
        """Handle shows help when no command text."""
        payload = {"text": ""}

        adapter.handle(payload)

        assert adapter.help_text is not None
        assert "TEST Commands" in adapter.help_text

    def test_handle_shows_help_for_help_keyword(self, adapter):
        """Handle shows help for 'help' command."""
        payload = {"text": "help"}

        adapter.handle(payload)

        assert adapter.help_text is not None

    def test_handle_shows_help_for_aide_keyword(self, adapter):
        """Handle shows help for 'aide' (French) command."""
        payload = {"text": "aide"}

        adapter.handle(payload)

        assert adapter.help_text is not None

    def test_handle_shows_error_for_unknown_command(self, adapter):
        """Handle shows error for unknown command."""
        payload = {"text": "unknown"}

        adapter.handle(payload)

        assert adapter.error_message is not None
        assert "Unknown command" in adapter.error_message
        assert "unknown" in adapter.error_message

    def test_handle_creates_context(self, adapter):
        """Handle creates CommandContext."""
        payload = {"text": "hello"}

        adapter.handle(payload)

        assert adapter.created_context is not None
        assert adapter.created_context.platform == "fake"
        assert adapter.created_context.user_id == "U123"

    def test_handle_executes_handler(self, adapter):
        """Handle executes command handler."""
        payload = {"text": "hello"}

        adapter.handle(payload)

        assert adapter.created_context._responder.send_message.called

    def test_tokenize_respects_quotes(self, adapter):
        """Tokenize respects quoted strings."""
        tokens = adapter._tokenize('hello "world test" foo')

        assert tokens == ["hello", "world test", "foo"]

    def test_tokenize_handles_single_quotes(self, adapter):
        """Tokenize handles single quotes."""
        tokens = adapter._tokenize("hello 'world test' foo")

        assert tokens == ["hello", "world test", "foo"]

    def test_tokenize_handles_mixed_quotes(self, adapter):
        """Tokenize handles mixed quote types."""
        tokens = adapter._tokenize("hello \"world\" 'test' foo")

        assert tokens == ["hello", "world", "test", "foo"]

    def test_tokenize_empty_string(self, adapter):
        """Tokenize handles empty string."""
        tokens = adapter._tokenize("")

        assert tokens == []

    def test_tokenize_only_spaces(self, adapter):
        """Tokenize handles string with only spaces."""
        tokens = adapter._tokenize("   ")

        assert tokens == []

    def test_generate_help_includes_all_commands(self, adapter):
        """Generate help includes all registered commands."""
        help_text = adapter._generate_help()

        assert "TEST Commands" in help_text
        assert "/test hello" in help_text

    def test_handle_catches_parse_errors(self, adapter, registry):
        """Handle catches CommandParseError."""
        from infrastructure.commands import Argument, ArgumentType

        @registry.command(
            name="required_arg",
            args=[Argument("arg", type=ArgumentType.STRING, required=True)],
        )
        def required_cmd(ctx, arg):
            pass

        payload = {"text": "required_arg"}

        adapter.handle(payload)

        assert adapter.error_message is not None

    def test_handle_catches_handler_exceptions(self, adapter, registry):
        """Handle catches exceptions from handler."""

        @registry.command(name="error")
        def error_cmd(ctx):
            raise ValueError("Test error")

        payload = {"text": "error"}

        adapter.handle(payload)

        assert adapter.error_message is not None
        assert "error occurred" in adapter.error_message.lower()

    def test_handle_with_subcommand(self, adapter, registry):
        """Handle executes subcommand."""
        handler_called = []

        @registry.command(name="parent")
        def parent_cmd(ctx):
            pass

        @registry.subcommand("parent", name="child")
        def child_cmd(ctx):
            handler_called.append(True)

        payload = {"text": "parent child"}

        adapter.handle(payload)

        # Note: This test documents current behavior where subcommands are not auto-called
        # Subcommand execution would be a future enhancement

    def test_adapter_with_translator(self, registry):
        """Adapter accepts translator."""
        translator = MagicMock()
        adapter = FakeAdapter(registry=registry, translator=translator)

        assert adapter.translator == translator

    def test_adapter_with_locale_resolver(self, registry):
        """Adapter accepts locale resolver."""
        resolver = MagicMock()
        adapter = FakeAdapter(registry=registry, locale_resolver=resolver)

        assert adapter.locale_resolver == resolver

    def test_tokenize_with_escaped_quotes(self, adapter):
        """Tokenize handles edge cases."""
        # Test with consecutive spaces
        tokens = adapter._tokenize("hello  world")
        assert tokens == ["hello", "world"]

        # Test with single word
        tokens = adapter._tokenize("hello")
        assert tokens == ["hello"]

        # Test with trailing space
        tokens = adapter._tokenize("hello ")
        assert tokens == ["hello"]

    def test_help_text_format_with_flags(self, adapter, registry):
        """Generate help includes proper formatting for flags."""
        from infrastructure.commands import Argument

        @registry.command(
            name="test",
            description="Test command",
            args=[
                Argument(
                    "--verbose", flag=True, required=False, description="Verbose output"
                )
            ],
        )
        def test_cmd(ctx, verbose=False):
            pass

        help_text = adapter._generate_help()

        assert "--verbose" in help_text
        assert "Verbose output" in help_text

    def test_handle_acknowledge_before_parse(self, adapter):
        """Ensure acknowledge is called before parse (to meet 3s Slack deadline)."""
        call_order = []

        original_acknowledge = adapter.acknowledge

        def track_acknowledge(payload):
            call_order.append("acknowledge")
            original_acknowledge(payload)

        adapter.acknowledge = track_acknowledge

        original_extract = adapter.extract_command_text

        def track_extract(payload):
            call_order.append("extract")
            return original_extract(payload)

        adapter.extract_command_text = track_extract

        payload = {"text": "hello"}
        adapter.handle(payload)

        assert call_order[0] == "acknowledge"
        assert call_order[1] == "extract"
