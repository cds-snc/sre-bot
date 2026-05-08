"""Slack bot service — owns transport lifecycle, command registration, and interaction binding."""

import threading
from typing import Any, Callable, Dict, Optional

import structlog
from slack_bolt import Ack, App, Respond
from slack_bolt.adapter.socket_mode import SocketModeHandler

from infrastructure.clients.slack import SlackSettings
from infrastructure.operations import OperationResult
from infrastructure.slack.formatter import SlackBlockKitFormatter
from infrastructure.slack.models import CommandPayload, CommandResponse
from infrastructure.slack.routing import CommandRouter

logger = structlog.get_logger()


class SlackBot:
    """Slack bot service.

    Lifecycle-managed — constructed in lifespan, not a DI singleton.
    Owns Bolt transport (App + SocketModeHandler) and is the registration
    surface for feature commands and interaction handlers.
    """

    def __init__(self, settings: SlackSettings, command_prefix: str = "") -> None:
        self._settings = settings
        self._token = settings.effective_bot_token or ""
        self._command_prefix = command_prefix
        self._app: Optional[App] = None
        self._handler: Optional[SocketModeHandler] = None
        self._socket_thread: Optional[threading.Thread] = None
        self._router = CommandRouter()
        self._formatter = SlackBlockKitFormatter()
        self._view_handlers: Dict[str, Callable[..., Any]] = {}
        self._action_handlers: Dict[str, Callable[..., Any]] = {}
        self._logger = logger.bind(component="slack_bot")

    def set_translator(self, translator: Callable) -> None:
        """Inject i18n translator into the command router."""
        self._router.set_translator(translator)

    @property
    def formatter(self) -> SlackBlockKitFormatter:
        """Block Kit formatter (also used for i18n injection at startup)."""
        return self._formatter

    @property
    def app(self) -> Optional[App]:
        """Bolt App instance, available after initialize_app()."""
        return self._app

    @property
    def socket_mode_handler(self) -> Optional[SocketModeHandler]:
        """Socket Mode handler, available after initialize_app() in socket mode."""
        return self._handler

    def initialize_app(self) -> OperationResult:
        """Initialize Bolt app, register slash commands, bind interaction handlers."""
        log = self._logger.bind(socket_mode=self._settings.SOCKET_MODE)
        log.info("initializing_slack_app")

        if self._settings.SOCKET_MODE and not self._settings.APP_TOKEN:
            log.error("missing_app_token")
            return OperationResult.permanent_error(
                message="APP_TOKEN required for Socket Mode",
                error_code="MISSING_APP_TOKEN",
            )

        if not self._token:
            log.error("missing_bot_token")
            return OperationResult.permanent_error(
                message="BOT_TOKEN is required",
                error_code="MISSING_BOT_TOKEN",
            )

        try:
            self._app = App(token=self._token)
            log.debug("slack_app_created")

            self._register_bolt_commands()

            for callback_id, handler in self._view_handlers.items():
                self._app.view(callback_id)(handler)
            for action_id, handler in self._action_handlers.items():
                self._app.action(action_id)(handler)

            if self._settings.SOCKET_MODE:
                self._handler = SocketModeHandler(self._app, self._settings.APP_TOKEN)
                log.info("socket_mode_handler_prepared")
            else:
                log.info("socket_mode_disabled_http_mode")

            log.info("slack_app_initialized")
            return OperationResult.success(
                data={"initialized": True, "socket_mode": self._settings.SOCKET_MODE},
                message="Slack app initialization completed",
            )

        except Exception as e:
            log.error("slack_app_initialization_failed", error=str(e))
            return OperationResult.permanent_error(
                message=f"Failed to initialize Slack app: {str(e)}",
                error_code="INITIALIZATION_ERROR",
            )

    def start(self) -> OperationResult:
        """Start Slack Socket Mode transport thread."""
        log = self._logger.bind(socket_mode=self._settings.SOCKET_MODE)

        if not self._settings.SOCKET_MODE:
            log.info("socket_mode_start_skipped")
            return OperationResult.success(message="Socket Mode disabled")

        if not self._handler:
            log.error("socket_mode_handler_missing")
            return OperationResult.permanent_error(
                message="Socket Mode handler not initialized",
                error_code="SOCKET_MODE_HANDLER_MISSING",
            )

        try:
            self._socket_thread = threading.Thread(
                target=self._handler.connect,
                daemon=True,
                name="slack-socket-mode",
            )
            self._socket_thread.start()
            log.info("socket_mode_started")
            return OperationResult.success(message="Socket Mode started")
        except Exception as e:
            log.error("socket_mode_start_failed", error=str(e))
            return OperationResult.permanent_error(
                message=f"Failed to start Socket Mode: {str(e)}",
                error_code="SOCKET_MODE_START_FAILED",
            )

    def stop(self) -> None:
        """Stop Socket Mode handler and join the transport thread."""
        if self._handler:
            self._handler.close()
        if self._socket_thread and self._socket_thread.is_alive():
            self._socket_thread.join(timeout=5)

    def register_command(
        self,
        command: str,
        handler: Optional[Callable[..., CommandResponse]],
        **kwargs: Any,
    ) -> None:
        """Register a command in the command tree.

        Accepts the same keyword arguments as CommandRouter.register().
        """
        self._router.register(command=command, handler=handler, **kwargs)
        self._logger.debug("slack_command_registered", command=command)

    def register_view_handler(
        self, callback_id: str, handler: Callable[..., Any]
    ) -> None:
        """Register a Slack view (modal) submission handler."""
        self._view_handlers[callback_id] = handler
        if self._app is not None:
            self._app.view(callback_id)(handler)

    def register_action_handler(
        self, action_id: str, handler: Callable[..., Any]
    ) -> None:
        """Register a Slack block action handler."""
        self._action_handlers[action_id] = handler
        if self._app is not None:
            self._app.action(action_id)(handler)

    def get_user_locale(self, user_id: str) -> str:
        """Resolve user locale from Slack API (requires initialized app)."""
        default_locale = "en-US"
        if not user_id or self._app is None:
            return default_locale
        try:
            user_info = self._app.client.users_info(user=user_id, include_locale=True)
            if user_info.get("ok") and user_info.get("user"):
                locale = user_info["user"].get("locale")
                if locale and isinstance(locale, str):
                    return locale
        except Exception as e:
            self._logger.warning(
                "failed_to_get_user_locale", user_id=user_id, error=str(e)
            )
        return default_locale

    def _register_bolt_commands(self) -> None:
        """Register root slash commands with Bolt based on the command tree."""
        if self._app is None:
            return

        for root_command in self._router.root_commands():
            slash_command = f"/{self._command_prefix}{root_command}"

            def create_handler(captured_root: str) -> Callable:
                def handler(
                    ack: Ack, command: Dict[str, Any], respond: Respond
                ) -> None:
                    ack()
                    payload = CommandPayload(
                        text="",
                        user_id=command.get("user_id", ""),
                        user_email=command.get("user_email"),
                        channel_id=command.get("channel_id"),
                        user_locale=command.get("locale", "en-US"),
                        response_url=command.get("response_url"),
                        platform_metadata=dict(command),
                    )
                    response = self._router.route(
                        root_command=captured_root,
                        text=command.get("text", ""),
                        payload=payload,
                    )
                    self._send_response(response, respond)

                return handler

            self._app.command(slash_command)(create_handler(root_command))
            self._logger.info(
                "registered_bolt_slash_command", slash_command=slash_command
            )

    @staticmethod
    def _send_response(response: CommandResponse, respond: Respond) -> None:
        response_type = "ephemeral" if response.ephemeral else "in_channel"
        if response.blocks:
            respond(
                text=response.message or "",
                blocks=response.blocks,
                response_type=response_type,
            )
        elif response.attachments:
            respond(
                text=response.message or "",
                attachments=response.attachments,
                response_type=response_type,
            )
        elif response.message:
            respond(text=response.message, response_type=response_type)
        else:
            respond(text="", response_type=response_type)
