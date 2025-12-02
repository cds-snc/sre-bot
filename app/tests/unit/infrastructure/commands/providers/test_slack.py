"""Unit tests for SlackCommandProvider."""

import pytest
from unittest.mock import MagicMock, patch


from infrastructure.commands.providers.slack import (
    SlackCommandProvider,
    SlackResponseChannel,
)
from infrastructure.commands.registry import CommandRegistry


class TestSlackResponseChannel:
    """Tests for SlackResponseChannel."""

    @pytest.fixture
    def mock_respond(self):
        """Mock Slack respond function."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Mock Slack client."""
        return MagicMock()

    @pytest.fixture
    def response_channel(self, mock_respond, mock_client):
        """Create SlackResponseChannel instance."""
        return SlackResponseChannel(
            respond=mock_respond,
            client=mock_client,
            channel_id="C123",
            user_id="U123",
        )

    def test_send_message_calls_respond(self, response_channel, mock_respond):
        """send_message calls respond function."""
        response_channel.send_message("test message")

        mock_respond.assert_called_once_with(text="test message")

    def test_send_message_passes_kwargs(self, response_channel, mock_respond):
        """send_message passes additional kwargs."""
        response_channel.send_message("test", blocks=[{"type": "section"}])

        mock_respond.assert_called_once_with(text="test", blocks=[{"type": "section"}])

    def test_send_ephemeral_calls_client(self, response_channel, mock_client):
        """send_ephemeral calls client.chat_postEphemeral."""
        response_channel.send_ephemeral("ephemeral message")

        mock_client.chat_postEphemeral.assert_called_once_with(
            channel="C123",
            user="U123",
            text="ephemeral message",
        )

    def test_send_ephemeral_passes_kwargs(self, response_channel, mock_client):
        """send_ephemeral passes additional kwargs."""
        response_channel.send_ephemeral("ephemeral", blocks=[{"type": "section"}])

        mock_client.chat_postEphemeral.assert_called_once_with(
            channel="C123",
            user="U123",
            text="ephemeral",
            blocks=[{"type": "section"}],
        )


class TestSlackCommandProvider:
    """Tests for SlackCommandProvider."""

    @pytest.fixture
    def registry(self):
        """Create test command registry."""
        reg = CommandRegistry("test")

        @reg.command(name="hello")
        def hello_cmd(ctx):
            ctx.respond("Hello!")

        return reg

    @pytest.fixture
    def mock_translator(self):
        """Mock translator."""
        translator = MagicMock()
        translator.translate.return_value = "translated text"
        return translator

    @pytest.fixture
    def mock_locale_resolver(self):
        """Mock locale resolver."""
        resolver = MagicMock()
        # New behavior: just use default_locale
        locale_enum = MagicMock()
        locale_enum.value = "en-US"
        resolver.default_locale = locale_enum
        return resolver

    @pytest.fixture
    def adapter(self, monkeypatch, mock_locale_resolver, mock_translator):
        """Create SlackCommandProvider instance with mocked settings.

        The new adapter signature takes config dict from settings,
        not registry/translator/resolver directly.
        """
        # Mock settings.slack.SLACK_TOKEN in the slack module
        mock_settings = MagicMock()
        mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"
        monkeypatch.setattr(
            "infrastructure.commands.providers.slack.settings", mock_settings
        )

        # Create adapter with config
        adapter = SlackCommandProvider(config={"enabled": True})

        # Attach mock registry, translator, and locale_resolver for testing
        adapter.registry = CommandRegistry("test")
        adapter.translator = mock_translator
        adapter.locale_resolver = mock_locale_resolver

        @adapter.registry.command(name="hello")
        def hello_cmd(ctx):
            ctx.respond("Hello!")

        return adapter

    @pytest.fixture
    def slack_payload(self):
        """Create mock Slack command payload."""
        return {
            "ack": MagicMock(),
            "command": {
                "text": "hello",
                "user_id": "U123",
                "user_name": "testuser",
                "channel_id": "C123",
                "team_id": "T123",
            },
            "client": MagicMock(),
            "respond": MagicMock(),
            "body": {"trigger_id": "trigger-123"},
        }

    def test_extract_command_text_returns_text(self, adapter, slack_payload):
        """extract_command_text returns command text."""
        text = adapter.extract_command_text(slack_payload)

        assert text == "hello"

    def test_extract_command_text_strips_whitespace(self, adapter, slack_payload):
        """extract_command_text strips whitespace."""
        slack_payload["command"]["text"] = "  hello  "

        text = adapter.extract_command_text(slack_payload)

        assert text == "hello"

    def test_extract_command_text_handles_empty(self, adapter, slack_payload):
        """extract_command_text handles empty text."""
        slack_payload["command"]["text"] = ""

        text = adapter.extract_command_text(slack_payload)

        assert text == ""

    def test_create_context_sets_platform(self, adapter, slack_payload):
        """create_context sets platform to 'slack'."""
        ctx = adapter.create_context(slack_payload)

        assert ctx.platform == "slack"

    def test_create_context_sets_user_id(self, adapter, slack_payload):
        """create_context sets user_id."""
        ctx = adapter.create_context(slack_payload)

        assert ctx.user_id == "U123"

    def test_create_context_sets_channel_id(self, adapter, slack_payload):
        """create_context sets channel_id."""
        ctx = adapter.create_context(slack_payload)

        assert ctx.channel_id == "C123"

    def test_create_context_fetches_user_email(self, adapter, slack_payload):
        """create_context fetches user email from Slack."""
        slack_payload["client"].users_info.return_value = {
            "ok": True,
            "user": {"profile": {"email": "test@example.com"}, "locale": "en-US"},
        }

        ctx = adapter.create_context(slack_payload)

        assert ctx.user_email == "test@example.com"
        assert slack_payload["client"].users_info.call_count == 2

    def test_create_context_handles_email_fetch_failure(self, adapter, slack_payload):
        """create_context handles failure to fetch email."""
        slack_payload["client"].users_info.side_effect = Exception("API error")

        ctx = adapter.create_context(slack_payload)

        assert ctx.user_email == ""

    def test_create_context_resolves_locale(self, adapter, slack_payload):
        """create_context resolves user locale from Slack."""
        slack_payload["client"].users_info.return_value = {
            "ok": True,
            "user": {"profile": {"email": "test@example.com"}, "locale": "fr-FR"},
        }

        ctx = adapter.create_context(slack_payload)

        # Locale should come from user profile
        assert ctx.locale == "fr-FR"

    def test_create_context_handles_locale_resolution_failure(
        self, monkeypatch, slack_payload
    ):
        """create_context handles locale resolution failure gracefully."""
        # Mock settings before provider init accesses it
        mock_settings = MagicMock()
        mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"
        monkeypatch.setattr(
            "infrastructure.commands.providers.slack.settings", mock_settings
        )

        # Create adapter
        adapter = SlackCommandProvider(config={"enabled": True})

        # Make users_info fail
        slack_payload["client"].users_info.side_effect = Exception("API error")

        ctx = adapter.create_context(slack_payload)

        # Should fall back to default locale
        assert ctx.locale == "en-US"

    def test_create_context_sets_metadata(self, adapter, slack_payload):
        """create_context sets metadata dict."""
        ctx = adapter.create_context(slack_payload)

        assert ctx.metadata["command"] == slack_payload["command"]
        assert ctx.metadata["client"] == slack_payload["client"]
        assert ctx.metadata["respond"] == slack_payload["respond"]

    def test_create_context_sets_responder(self, adapter, slack_payload):
        """create_context sets response channel."""
        ctx = adapter.create_context(slack_payload)

        assert ctx._responder is not None  # pylint: disable=protected-access
        assert isinstance(
            ctx._responder, SlackResponseChannel
        )  # pylint: disable=protected-access

    def test_create_context_sets_translator(self, adapter, slack_payload):
        """create_context sets translator to a callable wrapper."""
        ctx = adapter.create_context(slack_payload)

        # Translator should be set (created by adapter if not already set)
        assert ctx._translator is not None  # pylint: disable=protected-access

    def test_acknowledge_calls_ack_function(self, adapter, slack_payload):
        """acknowledge calls Slack ack function."""
        adapter.acknowledge(slack_payload)

        slack_payload["ack"].assert_called_once()

    def test_send_error_calls_respond_with_error_icon(self, adapter, slack_payload):
        """send_error calls respond with :x: icon."""
        adapter.send_error(slack_payload, "test error")

        slack_payload["respond"].assert_called_once_with(text=":x: test error")

    def test_send_help_calls_respond(self, adapter, slack_payload):
        """send_help calls respond with help text."""
        adapter.send_help(slack_payload, "help text")

        slack_payload["respond"].assert_called_once_with(text="help text")

    def test_handle_supports_payload_dict_signature(self, adapter, slack_payload):
        """handle supports payload dict signature."""
        adapter.handle(slack_payload)

        slack_payload["ack"].assert_called_once()
        slack_payload["respond"].assert_called()

    def test_handle_executes_command_handler(self, adapter, slack_payload):
        """handle executes command handler."""
        handler_called = []

        @adapter.registry.command(name="test")
        def test_cmd(ctx):  # pylint: disable=unused-argument
            handler_called.append(True)

        slack_payload["command"]["text"] = "test"

        adapter.handle(slack_payload)

        assert len(handler_called) == 1

    def test_adapter_initialization_without_translator(self, monkeypatch):
        """Adapter can initialize without translator (set to None initially)."""
        # Mock settings before provider init accesses it
        mock_settings = MagicMock()
        mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"
        monkeypatch.setattr(
            "infrastructure.commands.providers.slack.settings", mock_settings
        )

        adapter = SlackCommandProvider(config={})

        # Adapter starts with translator=None, will be set by create_context
        assert adapter.translator is None

    def test_adapter_initialization_without_locale_resolver(self, monkeypatch):
        """Adapter can initialize without locale_resolver (set to None initially)."""
        # Mock settings before provider init accesses it
        mock_settings = MagicMock()
        mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"
        monkeypatch.setattr(
            "infrastructure.commands.providers.slack.settings", mock_settings
        )

        adapter = SlackCommandProvider(config={})

        # Adapter starts with locale_resolver=None, will be set by create_context
        assert adapter.locale_resolver is None

    def test_create_context_handles_missing_client(self, adapter, slack_payload):
        """create_context raises error when client is missing."""
        slack_payload["client"] = None

        with pytest.raises(ValueError, match="Slack client required"):
            adapter.create_context(slack_payload)

    def test_create_context_handles_missing_command_dict(self, adapter):
        """create_context handles missing command dict."""
        payload = {
            "ack": MagicMock(),
            "command": {},
            "client": MagicMock(),
            "respond": MagicMock(),
            "body": {},
        }
        payload["client"].users_info.return_value = {"ok": False}

        ctx = adapter.create_context(payload)

        assert ctx.user_id == ""
        assert ctx.channel_id == ""

    def test_handle_with_command_arguments(self, adapter, slack_payload):
        """handle passes arguments to command handler."""
        from infrastructure.commands import Argument, ArgumentType

        captured_args = {}

        @adapter.registry.command(
            name="greet",
            args=[Argument("name", type=ArgumentType.STRING, required=True)],
        )
        def greet_cmd(ctx, name):  # pylint: disable=unused-argument
            captured_args["name"] = name

        slack_payload["command"]["text"] = "greet Alice"

        adapter.handle(slack_payload)

        assert captured_args.get("name") == "Alice"

    def test_validate_payload_missing_slack_token(self, adapter, slack_payload):
        """_validate_payload raises error when SLACK_TOKEN is missing."""
        # Mock settings to have empty SLACK_TOKEN
        with patch(
            "infrastructure.commands.providers.slack.settings.slack.SLACK_TOKEN", ""
        ):
            with pytest.raises(ValueError, match="SLACK_TOKEN required"):
                adapter._validate_payload(slack_payload)

    def test_handle_missing_slack_token_sends_error(self, adapter, slack_payload):
        """handle sends error response when SLACK_TOKEN is missing."""
        # Mock settings to have empty SLACK_TOKEN
        with patch(
            "infrastructure.commands.providers.slack.settings.slack.SLACK_TOKEN", ""
        ):
            adapter.handle(slack_payload)

            # Verify error was sent
            respond = slack_payload["respond"]
            assert respond.called
            call_args = respond.call_args
            assert (
                "error" in str(call_args).lower() or "token" in str(call_args).lower()
            )
