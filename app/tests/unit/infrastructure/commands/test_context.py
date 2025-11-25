"""Unit tests for CommandContext."""


class TestCommandContextCreation:
    """Tests for CommandContext creation."""

    def test_context_creation_with_defaults(self, command_context_factory):
        """CommandContext can be created with minimal parameters."""
        ctx = command_context_factory()

        assert ctx.platform == "slack"
        assert ctx.user_id == "U12345"
        assert ctx.user_email == "test@example.com"
        assert ctx.channel_id == "C12345"
        assert ctx.locale == "en-US"
        assert ctx.correlation_id is not None
        assert ctx.metadata == {}

    def test_context_creation_with_custom_values(self, command_context_factory):
        """CommandContext accepts custom values."""
        ctx = command_context_factory(
            platform="teams",
            user_id="U999",
            user_email="alice@example.com",
            channel_id="C999",
            locale="fr-FR",
        )

        assert ctx.platform == "teams"
        assert ctx.user_id == "U999"
        assert ctx.user_email == "alice@example.com"
        assert ctx.channel_id == "C999"
        assert ctx.locale == "fr-FR"

    def test_context_with_metadata(self, command_context_factory):
        """CommandContext can store metadata."""
        metadata = {"key": "value", "count": 42}
        ctx = command_context_factory(metadata=metadata)

        assert ctx.metadata == metadata

    def test_context_correlation_id_generated(self, command_context_factory):
        """CommandContext generates correlation_id if not provided."""
        ctx1 = command_context_factory()
        ctx2 = command_context_factory()

        assert ctx1.correlation_id is not None
        assert ctx2.correlation_id is not None
        assert ctx1.correlation_id != ctx2.correlation_id

    def test_context_correlation_id_preserved(self, command_context_factory):
        """CommandContext preserves provided correlation_id."""
        cid = "test-correlation-id"
        ctx = command_context_factory(correlation_id=cid)

        assert ctx.correlation_id == cid


class TestCommandContextTranslation:
    """Tests for translation methods."""

    def test_translate_with_translator(self, command_context_factory, mock_translator):
        """Context uses translator when set."""
        ctx = command_context_factory(translator=mock_translator, locale="en-US")

        result = ctx.translate("groups.success.add", email="test@example.com")

        assert "translated[en-US]:groups.success.add" in result
        assert "email=test@example.com" in result

    def test_translate_without_translator(self, command_context_factory):
        """Context returns key if translator not set."""
        ctx = command_context_factory(translator=None)

        result = ctx.translate("groups.success.add")

        assert result == "groups.success.add"

    def test_translate_respects_locale(self, command_context_factory, mock_translator):
        """Context passes correct locale to translator."""
        ctx = command_context_factory(translator=mock_translator, locale="fr-FR")

        result = ctx.translate("groups.success.add")

        assert "translated[fr-FR]" in result


class TestCommandContextResponding:
    """Tests for response methods."""

    def test_respond_sends_message(
        self, command_context_factory, mock_response_channel
    ):
        """respond calls responder.send_message."""
        ctx = command_context_factory(responder=mock_response_channel)

        ctx.respond("Hello, world!")

        mock_response_channel.send_message.assert_called_once_with("Hello, world!")

    def test_respond_without_responder(self, command_context_factory):
        """respond gracefully handles missing responder."""
        ctx = command_context_factory(responder=None)

        # Should not raise
        ctx.respond("Hello")

    def test_respond_ephemeral_sends_ephemeral(
        self, command_context_factory, mock_response_channel
    ):
        """respond_ephemeral calls responder.send_ephemeral."""
        ctx = command_context_factory(responder=mock_response_channel)

        ctx.respond_ephemeral("This is ephemeral")

        mock_response_channel.send_ephemeral.assert_called_once_with(
            "This is ephemeral"
        )

    def test_respond_ephemeral_without_responder(self, command_context_factory):
        """respond_ephemeral gracefully handles missing responder."""
        ctx = command_context_factory(responder=None)

        # Should not raise
        ctx.respond_ephemeral("Ephemeral message")

    def test_respond_with_kwargs(self, command_context_factory, mock_response_channel):
        """respond passes through kwargs to responder."""
        ctx = command_context_factory(responder=mock_response_channel)

        ctx.respond("Message", thread_ts="123.456", blocks=[])

        mock_response_channel.send_message.assert_called_once_with(
            "Message", thread_ts="123.456", blocks=[]
        )


class TestCommandContextLogging:
    """Tests for logging integration."""

    def test_get_logger_returns_bound_logger(self, command_context_factory):
        """get_logger returns logger with context bound."""
        ctx = command_context_factory(
            platform="slack",
            user_id="U123",
            channel_id="C456",
            correlation_id="corr-789",
        )

        logger = ctx.get_logger()

        assert logger is not None
        # Check that context was bound (via the bound attributes)
        # Note: This is a bit tricky to test without internal access to structlog
        # but we can at least verify the method returns something


class TestCommandContextIntegration:
    """Integration tests for CommandContext."""

    def test_context_lifecycle(
        self, command_context_factory, mock_translator, mock_response_channel
    ):
        """Test complete context lifecycle."""
        ctx = command_context_factory(
            translator=mock_translator,
            responder=mock_response_channel,
            locale="en-US",
        )

        # Translate and respond
        msg = ctx.translate("groups.success.add", email="alice@example.com")
        ctx.respond(msg)

        # Verify translator was called
        assert "translated[en-US]" in msg
        # Verify responder was called
        mock_response_channel.send_message.assert_called_once()

    def test_multiple_responses_in_sequence(
        self, command_context_factory, mock_response_channel
    ):
        """Context can send multiple responses."""
        ctx = command_context_factory(responder=mock_response_channel)

        ctx.respond("First message")
        ctx.respond("Second message")
        ctx.respond_ephemeral("Ephemeral message")

        assert mock_response_channel.send_message.call_count == 2
        assert mock_response_channel.send_ephemeral.call_count == 1
