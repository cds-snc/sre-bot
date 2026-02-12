"""Slack platform provider implementation.

Provides integration with Slack using the Bolt SDK for Socket Mode.
"""

import threading
from typing import Any, Callable, Dict, FrozenSet, List, Optional

import structlog
from slack_bolt import Ack, App, Respond
from slack_bolt.adapter.socket_mode import SocketModeHandler

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.models import (
    CommandDefinition,
    CommandPayload,
    CommandResponse,
)
from infrastructure.platforms.parsing import CommandArgumentParser
from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.utils.slack_help import (
    SLACK_HELP_KEYWORDS,
    SlackHelpGenerator,
)

logger = structlog.get_logger()


class SlackPlatformProvider(BasePlatformProvider):
    """Slack platform provider using Bolt SDK with Socket Mode.

    Provides core functionality for:
    - Sending messages with Block Kit formatting
    - Socket Mode connection management
    - Capability declaration (commands, interactive cards, views)
    - Response formatting using SlackBlockKitFormatter

    Example:
        from infrastructure.configuration import SlackPlatformSettings
        from infrastructure.platforms.formatters.slack import (
            SlackBlockKitFormatter
        )

        settings = SlackPlatformSettings(
            ENABLED=True,
            SOCKET_MODE=True,
            APP_TOKEN="xapp-...",
            BOT_TOKEN="xoxb-...",
        )
        formatter = SlackBlockKitFormatter()
        provider = SlackPlatformProvider(
            settings=settings,
            formatter=formatter,
        )

        # Send message
        result = provider.send_message(
            channel="C123",
            message={"text": "Hello"},
        )
    """

    SLACK_HELP_KEYWORDS = SLACK_HELP_KEYWORDS

    def __init__(
        self,
        settings,  # SlackPlatformSettings type
        formatter: Optional[SlackBlockKitFormatter] = None,
        name: str = "slack",
        version: str = "1.0.0",
    ):
        """Initialize Slack platform provider.

        Args:
            settings: SlackPlatformSettings instance with tokens and config
            formatter: Optional SlackBlockKitFormatter for response formatting
            name: Provider name (default: "slack")
            version: Provider version (default: "1.0.0")
        """
        super().__init__(
            name=name,
            version=version,
            enabled=settings.ENABLED,
        )

        self._settings = settings
        self._formatter = formatter or SlackBlockKitFormatter()

        # Will be initialized when app is started
        self._app: Optional[App] = None
        self._client: Optional[Any] = None

        # Help generator for unified help text generation
        self._help_generator = SlackHelpGenerator(
            commands=self._commands,
            translator=self._translate_or_fallback,
        )

        self._logger.info(
            "slack_provider_initialized",
            socket_mode=settings.SOCKET_MODE,
            enabled=settings.ENABLED,
        )
        self._handler: Optional[SocketModeHandler] = (
            None  # Socket Mode handler reference
        )
        self._socket_thread: Optional[threading.Thread] = None

    def get_capabilities(self) -> CapabilityDeclaration:
        """Get Slack platform capabilities.

        Returns:
            CapabilityDeclaration with supported Slack capabilities
        """
        return create_capability_declaration(
            "slack",
            PlatformCapability.COMMANDS,
            PlatformCapability.INTERACTIVE_CARDS,
            PlatformCapability.VIEWS_MODALS,
            PlatformCapability.THREADS,
            PlatformCapability.REACTIONS,
            PlatformCapability.FILE_SHARING,
            PlatformCapability.HIERARCHICAL_TEXT_COMMANDS,
            metadata={
                "socket_mode": self._settings.SOCKET_MODE,
                "platform": "slack",
                "connection_mode": "websocket",
                "command_parsing": "hierarchical_text",
            },
        )

    def get_webhook_router(self):
        """Get webhook router for Slack.

        Slack uses Socket Mode (WebSocket), so no HTTP webhooks are needed.

        Returns:
            None (WebSocket mode, not HTTP)
        """
        return None  # Slack uses Socket Mode (WebSocket), not HTTP webhooks

    def get_help_keywords(self) -> FrozenSet[str]:
        """Get Slack-specific help keywords for text commands."""
        return self.SLACK_HELP_KEYWORDS

    def initialize_app(self) -> OperationResult:
        """Initialize Slack Bolt app with Socket Mode handler.

        Sets up:
        - Bolt App instance
        - Socket Mode handler (if enabled)

        Note: Command handlers are registered separately via register_command()
        or by the application layer (e.g., main.py) directly with the app.

        Returns:
            OperationResult with initialization status
        """
        log = self._logger.bind(socket_mode=self._settings.SOCKET_MODE)
        log.info("initializing_slack_app")

        if not self._settings.ENABLED:
            log.warning("slack_disabled_skipping_init")
            return OperationResult.permanent_error(
                message="Slack provider is disabled",
                error_code="PROVIDER_DISABLED",
            )

        # Validate required tokens
        if self._settings.SOCKET_MODE:
            if not self._settings.APP_TOKEN:
                log.error("missing_app_token")
                return OperationResult.permanent_error(
                    message="APP_TOKEN required for Socket Mode",
                    error_code="MISSING_APP_TOKEN",
                )

        if not self._settings.BOT_TOKEN:
            log.error("missing_bot_token")
            return OperationResult.permanent_error(
                message="BOT_TOKEN is required",
                error_code="MISSING_BOT_TOKEN",
            )

        try:
            # Create Bolt App instance
            self._app = App(token=self._settings.BOT_TOKEN)
            self._client = self._app.client
            log.debug("slack_app_created")

            # Auto-register root commands with Slack Bolt
            # Extract unique root commands from registered command tree
            # (e.g., "sre" from "sre.incident", "sre.webhooks", etc.)
            self._auto_register_root_commands()

            # Prepare Socket Mode handler if enabled (start happens separately)
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
        """Start Slack Socket Mode if enabled."""
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
        """Stop Slack Socket Mode handler if running."""
        if self._handler:
            self._handler.close()
        if self._socket_thread and self._socket_thread.is_alive():
            self._socket_thread.join(timeout=5)

    def _auto_register_root_commands(self) -> None:
        """Auto-register root commands with Slack Bolt based on registered command tree.

        Analyzes self._commands to extract unique root commands (e.g., "sre" from "sre.incident")
        and registers Slack Bolt handlers for them that delegate to route_hierarchical_command().

        This eliminates the need for manual @bot.command("/sre") registrations in modules/.

        Example:
            After packages register:
            - provider.register_command("incident", parent="sre", ...)
            - provider.register_command("webhooks", parent="sre", ...)

            This method auto-detects "/sre" is needed and registers:
            @bot.command("/sre")
            def handle_sre(ack, command, respond):
                # Calls route_hierarchical_command("sre", ...)
        """
        if not self._app:
            self._logger.warning("app_not_initialized_skipping_root_registration")
            return

        # Extract unique root commands from command tree
        root_commands = set()
        for full_path in self._commands.keys():
            # Extract root from paths like "sre.incident", "sre.webhooks" → "sre"
            root = full_path.split(".")[0]
            root_commands.add(root)

        # Register each root command with Slack Bolt
        for root_command in sorted(root_commands):
            # Build slash command (e.g., /sre, /geolocate)
            slash_command = f"/{root_command}"

            # Create handler closure that captures root_command
            def create_handler(captured_root: str):
                def handler(ack: Ack, command: Dict[str, Any], respond: Respond):
                    """Auto-generated root command handler."""
                    ack()

                    # Create base payload from Slack command
                    payload = CommandPayload(
                        text="",  # Will be set by route_hierarchical_command
                        user_id=command.get("user_id", ""),
                        user_email=command.get("user_email"),
                        channel_id=command.get("channel_id"),
                        user_locale=command.get("locale", "en-US"),
                        response_url=command.get("response_url"),
                        platform_metadata=dict(command),
                    )

                    # Route through provider's hierarchical command handler
                    response = self.route_hierarchical_command(
                        root_command=captured_root,
                        text=command.get("text", ""),
                        payload=payload,
                    )

                    # Send response back to Slack
                    self._send_command_response(response, respond)

                return handler

            # Register the handler with Slack Bolt
            self._app.command(slash_command)(create_handler(root_command))

            self._logger.info(
                "auto_registered_root_command",
                slash_command=slash_command,
                root=root_command,
            )

    def _tokenize_command_text(self, text: str) -> List[str]:
        """Tokenize Slack command text using quote-aware parsing."""
        parser = CommandArgumentParser([])
        return parser._tokenize(text)

    def route_hierarchical_command(
        self, root_command: str, text: str, payload: CommandPayload
    ) -> CommandResponse:
        """Route a Slack hierarchical command recursively to leaf command.

        Handles multi-level command hierarchies by recursively routing through
        the command tree. Uses quote-aware tokenization to preserve arguments
        with spaces.

        Flow:
        1. Tokenize text (quote-aware)
        2. Check if first token is help keyword → generate help
        3. Check if first token matches child command → recurse
        4. If no match or no tokens, dispatch to current command

        Args:
            root_command: Current command path (e.g., "sre" or "sre.groups")
            text: Flattened text from Slack (e.g., "groups list --managed")
            payload: CommandPayload with user context

        Returns:
            CommandResponse from handler or auto-generated help

        Example:
            User: /sre groups add email@example.com
            Call: route_hierarchical_command("sre", "groups add email@example.com")
            Internal routing:
              - "sre" + "groups" → "sre.groups" (child found, recurse)
              - "sre.groups" + "add" → "sre.groups.add" (child found, recurse)
              - "sre.groups.add" + "email@..." → no child (dispatch)
            Handler receives: text="email@example.com" (arguments only)
        """
        if not text or not text.strip():
            return self.dispatch_command(root_command, payload)

        tokens = self._tokenize_command_text(text)
        if not tokens:
            return self.dispatch_command(root_command, payload)

        first_word = tokens[0]
        remaining_text = " ".join(tokens[1:]) if len(tokens) > 1 else ""

        # Check for help keyword (early exit, don't recurse deeper)
        if first_word.lower() in self.SLACK_HELP_KEYWORDS:
            payload.text = first_word
            return self.dispatch_command(root_command, payload)

        # Try to recurse to child command
        child_path = f"{root_command}.{first_word}"
        if child_path in self._commands:
            payload.text = remaining_text
            # Recursively route the child to handle arbitrary depth
            return self.route_hierarchical_command(child_path, remaining_text, payload)

        # No child found, dispatch to current command with full text
        payload.text = text
        return self.dispatch_command(root_command, payload)

    def _send_command_response(
        self, response: CommandResponse, respond: Respond
    ) -> None:
        """Send CommandResponse to Slack using respond function.

        Args:
            response: CommandResponse from handler
            respond: Slack Bolt respond function
        """
        response_type = "ephemeral" if response.ephemeral else "in_channel"

        if response.blocks:
            respond(
                text=response.message or "",
                blocks=response.blocks,
                response_type=response_type,
            )
            return

        if response.attachments:
            respond(
                text=response.message or "",
                attachments=response.attachments,
                response_type=response_type,
            )
            return

        if response.message:
            respond(text=response.message, response_type=response_type)
            return

        respond(text="", response_type=response_type)

    @property
    def formatter(self) -> SlackBlockKitFormatter:
        """Get the Slack Block Kit formatter.

        Returns:
            SlackBlockKitFormatter instance
        """
        return self._formatter

    @property
    def settings(self):
        """Get Slack platform settings.

        Returns:
            SlackPlatformSettings instance
        """
        return self._settings

    @property
    def app(self):
        """Get the Slack Bolt App instance.

        Returns:
            Slack Bolt App instance (or None if not yet initialized)

        Note:
            For legacy support during gradual migration, modules can access
            the managed Bolt app for registering legacy handlers.
        """
        return self._app

    @property
    def socket_mode_handler(self) -> Optional[SocketModeHandler]:
        """Get the Socket Mode handler if initialized."""
        return self._handler

    def get_user_locale(self, user_id: str) -> str:
        """Get user's locale from Slack API.

        Extracts the user's locale preference from their Slack profile.
        Falls back to "en-US" if locale cannot be determined.

        Args:
            user_id: Slack user ID (e.g., "U02KULRUCA2")

        Returns:
            Locale string (e.g., "en-US", "fr-FR")
        """
        default_locale = "en-US"
        supported_locales = ["en-US", "fr-FR"]

        if not user_id:
            return default_locale

        if not self._client:
            self._logger.warning(
                "slack_client_not_available_for_locale_extraction",
                user_id=user_id,
            )
            return default_locale

        try:
            user_info = self._client.users_info(user=user_id, include_locale=True)
            if user_info.get("ok") and user_info.get("user"):
                user_locale = user_info["user"].get("locale")
                if user_locale and user_locale in supported_locales:
                    self._logger.debug(
                        "user_locale_extracted_from_slack",
                        user_id=user_id,
                        locale=user_locale,
                    )
                    return user_locale
                else:
                    self._logger.debug(
                        "user_locale_not_supported_or_missing",
                        user_id=user_id,
                        locale=user_locale,
                        supported=supported_locales,
                    )
            else:
                self._logger.warning(
                    "slack_users_info_failed",
                    user_id=user_id,
                    ok=user_info.get("ok"),
                )
        except Exception as e:
            self._logger.warning(
                "failed_to_get_user_locale_from_slack",
                user_id=user_id,
                error=str(e),
            )

        return default_locale

    def register_command(
        self,
        command: str,
        handler: Callable[..., CommandResponse],
        description: str = "",
        description_key: Optional[str] = None,
        usage_hint: str = "",
        examples: Optional[list] = None,
        example_keys: Optional[list] = None,
        parent: Optional[str] = None,
        legacy_mode: bool = False,
        arguments: Optional[list] = None,
        schema: Optional[type] = None,
        argument_mapper: Optional[Callable] = None,
        fallback_handler: Optional[Callable[[CommandPayload], CommandResponse]] = None,
    ) -> None:
        """Register a Slack command with hierarchical support and argument parsing.

        Automatically creates intermediate command nodes if parent uses dot notation.
        Supports rich argument parsing with type validation and schema mapping.

        Args:
            command: Command name (e.g., "aws", "test-connection")
            handler: Function that handles CommandPayload → CommandResponse
            description: English description (fallback if translation unavailable)
            description_key: i18n translation key (e.g., "commands.aws.description")
            usage_hint: Usage string (e.g., "<account_id>")
            examples: List of example argument strings
            example_keys: List of translation keys for examples
            parent: Dot notation parent path (e.g., "sre.dev")
            legacy_mode: If True, bypass automatic help interception (for gradual migration)
            arguments: List of Argument definitions for parsing (from infrastructure.platforms.parsing)
            schema: Pydantic BaseModel schema for validation
            argument_mapper: Function to transform parsed args Dict to schema fields Dict
            fallback_handler: Optional handler called when command expects arguments but none provided

        Example:
            # Simple command
            provider.register_command(
                command="version",
                handler=handle_version,
                description="Show version",
                parent="sre",
            )

            # With argument parsing
            from infrastructure.platforms.parsing import Argument, ArgumentType

            provider.register_command(
                command="list",
                handler=handle_groups_list,
                parent="sre.groups",
                arguments=[
                    Argument(name="--provider", type=ArgumentType.CHOICE, choices=["aws", "google"]),
                    Argument(name="--include-members", type=ArgumentType.BOOLEAN),
                ],
                schema=ListGroupsRequest,
                argument_mapper=lambda parsed: {"provider": parsed.get("--provider")},
            )
        """
        # Auto-generate intermediate nodes if parent specified
        if parent:
            self._ensure_parent_chain_exists(parent)

        # Create the command definition
        cmd_def = CommandDefinition(
            name=command,
            handler=handler,
            description=description,
            description_key=description_key,
            usage_hint=usage_hint,
            examples=examples or [],
            example_keys=example_keys or [],
            parent=parent,
            legacy_mode=legacy_mode,
            arguments=arguments,
            schema=schema,
            argument_mapper=argument_mapper,
            fallback_handler=fallback_handler,
        )

        # Store by full_path
        self._commands[cmd_def.full_path] = cmd_def

        self._logger.debug(
            "slack_command_registered",
            command=command,
            parent=parent,
            full_path=cmd_def.full_path,
            has_description=bool(description or description_key),
        )

    def generate_help(
        self,
        locale: str = "en-US",
        root_command: Optional[str] = None,
    ) -> str:
        """Generate Slack-formatted help text for registered commands.

        Delegates to SlackHelpGenerator for unified help generation.
        Supports hierarchical command display using the dot notation.
        Uses Slack markdown formatting (backticks, asterisks, bullet points).

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")
            root_command: Optional root command full_path (e.g., "sre.dev")
                         to filter help to only its children. If None, shows
                         all top-level commands.

        Returns:
            Slack-formatted help text with commands and examples

        Example Output:
            ```
            *Available Commands*

            • `/sre` - SRE Operations
            • `/sre dev` - Development tools
              • `/sre dev aws` - AWS development commands
            ```
        """
        return self._help_generator.generate(
            root_command, mode="tree" if root_command else None
        ) or self._help_generator.generate(None, mode="tree")

    def generate_command_help(self, command_name: str, locale: str = "en-US") -> str:
        """Generate Slack-formatted help text for a specific command.

        Delegates to SlackHelpGenerator for unified help generation.
        Uses Slack markdown formatting (backticks, asterisks, bullet points).

        Args:
            command_name: Full path of the command (e.g., "sre.dev.aws")
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Slack-formatted help text for the specified command
        """
        return self._help_generator.generate(command_name, mode="command")
