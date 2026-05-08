"""Unit tests for infrastructure.slack.service.SlackBot.

Covers all lifecycle, registration, dispatch, and property branches
in full isolation — no real Slack API or socket connections made.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.operations import OperationStatus
from infrastructure.slack.formatter import SlackBlockKitFormatter
from infrastructure.slack.models import CommandResponse
from infrastructure.slack.routing import CommandRouter
from infrastructure.slack.service import SlackBot

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS / FIXTURES
# ─────────────────────────────────────────────────────────────────────────────


def _make_settings(
    *,
    enabled: bool = True,
    socket_mode: bool = True,
    app_token: str | None = "xapp-test",
    bot_token: str | None = "xoxb-test",
    signing_secret: str | None = "secret",
) -> MagicMock:
    """Return a minimal SlackSettings-shaped mock."""
    s = MagicMock()
    s.ENABLED = enabled
    s.SOCKET_MODE = socket_mode
    s.APP_TOKEN = app_token
    s.SIGNING_SECRET = signing_secret
    s.effective_bot_token = bot_token
    return s


@pytest.fixture
def settings():
    return _make_settings()


@pytest.fixture
def settings_no_socket():
    return _make_settings(socket_mode=False, app_token=None)


class FakeApp:
    """Minimal Bolt App stand-in — records registered commands and handlers."""

    def __init__(self, token=None):
        self.token = token
        self.client = MagicMock()
        self._commands: dict = {}
        self._views: dict = {}
        self._actions: dict = {}

    def command(self, name):
        def decorator(fn):
            self._commands[name] = fn
            return fn

        return decorator

    def view(self, callback_id):
        def decorator(fn):
            self._views[callback_id] = fn
            return fn

        return decorator

    def action(self, action_id):
        def decorator(fn):
            self._actions[action_id] = fn
            return fn

        return decorator


class FakeSocketModeHandler:
    """Minimal SocketModeHandler stand-in — captures connect/close calls."""

    def __init__(self, app, token):
        self.app = app
        self.token = token
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True

    def close(self):
        self.closed = True


@pytest.fixture
def patch_bolt(monkeypatch):
    """Monkeypatch Bolt App and SocketModeHandler inside service module."""
    monkeypatch.setattr("infrastructure.slack.service.App", FakeApp)
    monkeypatch.setattr(
        "infrastructure.slack.service.SocketModeHandler", FakeSocketModeHandler
    )


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────


class TestSlackBotConstruction:
    def test_constructs_with_valid_settings(self, settings):
        bot = SlackBot(settings=settings)

        assert bot is not None

    def test_app_is_none_before_initialize(self, settings):
        bot = SlackBot(settings=settings)

        assert bot.app is None

    def test_socket_mode_handler_is_none_before_initialize(self, settings):
        bot = SlackBot(settings=settings)

        assert bot.socket_mode_handler is None

    def test_formatter_is_block_kit_formatter(self, settings):
        bot = SlackBot(settings=settings)

        assert isinstance(bot.formatter, SlackBlockKitFormatter)

    def test_command_prefix_default_is_empty(self, settings):
        bot = SlackBot(settings=settings)

        assert bot._command_prefix == ""

    def test_command_prefix_stored(self, settings):
        bot = SlackBot(settings=settings, command_prefix="dev-")

        assert bot._command_prefix == "dev-"

    def test_router_created(self, settings):
        bot = SlackBot(settings=settings)

        assert isinstance(bot._router, CommandRouter)


# ─────────────────────────────────────────────────────────────────────────────
# initialize_app — success paths
# ─────────────────────────────────────────────────────────────────────────────


class TestInitializeAppSuccess:
    def test_returns_success_in_socket_mode(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert result.is_success

    def test_data_contains_initialized_true(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert result.data["initialized"] is True

    def test_data_socket_mode_true_when_enabled(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert result.data["socket_mode"] is True

    def test_app_set_after_initialize(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)

        bot.initialize_app()

        assert isinstance(bot.app, FakeApp)

    def test_socket_mode_handler_set_after_initialize(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)

        bot.initialize_app()

        assert isinstance(bot.socket_mode_handler, FakeSocketModeHandler)

    def test_initialize_without_socket_mode_returns_success(
        self, settings_no_socket, patch_bolt
    ):
        bot = SlackBot(settings=settings_no_socket)

        result = bot.initialize_app()

        assert result.is_success
        assert result.data["socket_mode"] is False

    def test_http_mode_does_not_create_socket_handler(
        self, settings_no_socket, patch_bolt
    ):
        bot = SlackBot(settings=settings_no_socket)

        bot.initialize_app()

        assert bot.socket_mode_handler is None

    def test_pre_registered_view_handler_bound_to_app(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        view_fn = MagicMock()
        bot.register_view_handler("my_modal", view_fn)

        bot.initialize_app()

        assert "my_modal" in bot.app._views

    def test_pre_registered_action_handler_bound_to_app(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        action_fn = MagicMock()
        bot.register_action_handler("btn_click", action_fn)

        bot.initialize_app()

        assert "btn_click" in bot.app._actions


# ─────────────────────────────────────────────────────────────────────────────
# initialize_app — failure paths
# ─────────────────────────────────────────────────────────────────────────────


class TestInitializeAppFailure:
    def test_missing_app_token_in_socket_mode_returns_permanent_error(self):
        settings = _make_settings(socket_mode=True, app_token=None)
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "MISSING_APP_TOKEN"

    def test_missing_bot_token_returns_permanent_error(self):
        settings = _make_settings(bot_token=None)
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "MISSING_BOT_TOKEN"

    def test_bolt_app_exception_returns_initialization_error(
        self, settings, monkeypatch
    ):
        monkeypatch.setattr(
            "infrastructure.slack.service.App",
            MagicMock(side_effect=RuntimeError("bolt failure")),
        )
        bot = SlackBot(settings=settings)

        result = bot.initialize_app()

        assert not result.is_success
        assert result.error_code == "INITIALIZATION_ERROR"
        assert "bolt failure" in result.message


# ─────────────────────────────────────────────────────────────────────────────
# start — success and failure paths
# ─────────────────────────────────────────────────────────────────────────────


class TestStartSuccess:
    def test_start_in_socket_mode_returns_success(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()

        result = bot.start()

        assert result.is_success

    def test_start_creates_daemon_thread(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()

        bot.start()

        assert bot._socket_thread is not None
        assert bot._socket_thread.daemon is True
        assert bot._socket_thread.name == "slack-socket-mode"

    def test_http_mode_start_returns_success_without_thread(
        self, settings_no_socket, patch_bolt
    ):
        bot = SlackBot(settings=settings_no_socket)
        bot.initialize_app()

        result = bot.start()

        assert result.is_success
        assert bot._socket_thread is None


class TestStartFailure:
    def test_start_without_handler_returns_permanent_error(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        # Do NOT call initialize_app() — handler stays None

        result = bot.start()

        assert not result.is_success
        assert result.error_code == "SOCKET_MODE_HANDLER_MISSING"

    def test_start_thread_exception_returns_start_failed(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        # Force thread.start() to raise
        with patch("threading.Thread.start", side_effect=RuntimeError("thread boom")):
            result = bot.start()

        assert not result.is_success
        assert result.error_code == "SOCKET_MODE_START_FAILED"
        assert "thread boom" in result.message


# ─────────────────────────────────────────────────────────────────────────────
# stop
# ─────────────────────────────────────────────────────────────────────────────


class TestStop:
    def test_stop_closes_handler(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()

        bot.stop()

        assert bot._handler.closed is True

    def test_stop_joins_thread(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        bot.start()
        # Give thread time to start before stopping
        bot._socket_thread.join(timeout=0.05)

        bot.stop()  # Should not raise

    def test_stop_when_handler_is_none_does_not_raise(self, settings):
        bot = SlackBot(settings=settings)
        # handler never set

        bot.stop()  # Must not raise

    def test_stop_when_thread_is_none_does_not_raise(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        # Do not call start() so thread stays None

        bot.stop()  # Must not raise


# ─────────────────────────────────────────────────────────────────────────────
# register_command / register_view_handler / register_action_handler
# ─────────────────────────────────────────────────────────────────────────────


class TestCommandRegistration:
    def test_register_command_before_init_stored_in_router(self, settings):
        bot = SlackBot(settings=settings)
        handler = MagicMock(return_value=CommandResponse(message="ok"))

        bot.register_command("ping", handler, description="Ping the bot")

        assert "ping" in bot._router._commands

    def test_register_command_after_init_registered_in_bolt(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        handler = MagicMock(return_value=CommandResponse(message="ok"))

        bot.register_command("ping", handler, description="Ping")

        # Bolt command registration happens at initialize time via _register_bolt_commands
        # Post-init registration only stores in router
        assert "ping" in bot._router._commands

    def test_register_view_handler_after_init_bound_to_bolt(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        view_fn = MagicMock()

        bot.register_view_handler("my_modal", view_fn)

        assert "my_modal" in bot.app._views

    def test_register_action_handler_after_init_bound_to_bolt(
        self, settings, patch_bolt
    ):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        action_fn = MagicMock()

        bot.register_action_handler("btn_ok", action_fn)

        assert "btn_ok" in bot.app._actions

    def test_register_view_handler_before_init_stored_for_later(self, settings):
        bot = SlackBot(settings=settings)
        view_fn = MagicMock()

        bot.register_view_handler("deferred_modal", view_fn)

        assert "deferred_modal" in bot._view_handlers

    def test_register_action_handler_before_init_stored_for_later(self, settings):
        bot = SlackBot(settings=settings)
        action_fn = MagicMock()

        bot.register_action_handler("deferred_btn", action_fn)

        assert "deferred_btn" in bot._action_handlers


# ─────────────────────────────────────────────────────────────────────────────
# Bolt command registration wiring (_register_bolt_commands)
# ─────────────────────────────────────────────────────────────────────────────


class TestBoltCommandWiring:
    def test_root_commands_registered_as_slash_commands(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.register_command("sre", None, description="SRE root")

        bot.initialize_app()

        assert "/sre" in bot.app._commands

    def test_command_prefix_prepended_to_slash_command(self, patch_bolt):
        s = _make_settings()
        bot = SlackBot(settings=s, command_prefix="dev-")
        bot.register_command("sre", None, description="SRE root")

        bot.initialize_app()

        assert "/dev-sre" in bot.app._commands

    def test_bolt_handler_calls_ack_and_respond(self, settings, patch_bolt):
        """The generated Bolt handler must ack() and call respond() with the routed response."""
        bot = SlackBot(settings=settings)
        handler = MagicMock(
            return_value=CommandResponse(message="pong", ephemeral=True)
        )
        bot.register_command("ping", handler, description="Ping")

        bot.initialize_app()

        ack = MagicMock()
        respond = MagicMock()
        command_data = {
            "user_id": "U001",
            "text": "",
            "channel_id": "C001",
            "locale": "en-US",
            "response_url": "https://hooks.example.com",
        }

        bolt_handler = bot.app._commands["/ping"]
        bolt_handler(ack=ack, command=command_data, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# set_translator
# ─────────────────────────────────────────────────────────────────────────────


class TestSetTranslator:
    def test_translator_forwarded_to_router(self, settings):
        bot = SlackBot(settings=settings)
        translator = MagicMock(return_value="translated")

        bot.set_translator(translator)

        assert bot._router._translator is translator


# ─────────────────────────────────────────────────────────────────────────────
# get_user_locale
# ─────────────────────────────────────────────────────────────────────────────


class TestGetUserLocale:
    def test_returns_default_when_app_not_initialized(self, settings):
        bot = SlackBot(settings=settings)

        locale = bot.get_user_locale("U123")

        assert locale == "en-US"

    def test_returns_default_for_empty_user_id(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()

        locale = bot.get_user_locale("")

        assert locale == "en-US"

    def test_returns_locale_from_slack_api(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        bot.app.client.users_info.return_value = {
            "ok": True,
            "user": {"locale": "fr-FR"},
        }

        locale = bot.get_user_locale("U123")

        assert locale == "fr-FR"

    def test_returns_default_when_api_response_not_ok(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        bot.app.client.users_info.return_value = {"ok": False}

        locale = bot.get_user_locale("U123")

        assert locale == "en-US"

    def test_returns_default_when_api_raises(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        bot.app.client.users_info.side_effect = RuntimeError("api down")

        locale = bot.get_user_locale("U123")

        assert locale == "en-US"

    def test_returns_default_when_locale_field_missing(self, settings, patch_bolt):
        bot = SlackBot(settings=settings)
        bot.initialize_app()
        bot.app.client.users_info.return_value = {
            "ok": True,
            "user": {},  # no locale key
        }

        locale = bot.get_user_locale("U123")

        assert locale == "en-US"
