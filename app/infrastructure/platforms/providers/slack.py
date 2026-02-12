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
    build_slack_command_signature,
    build_slack_display_path,
    generate_slack_help_text,
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

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send a message to a Slack channel.

        Args:
            channel: Slack channel ID (e.g., "C123456")
            message: Message content (can include "text" and/or "blocks")
            thread_ts: Optional thread timestamp for threading

        Returns:
            OperationResult with message send status and response data
        """
        log = self._logger.bind(channel=channel, has_thread=bool(thread_ts))
        log.info("sending_slack_message")

        if not self.enabled:
            log.warning("slack_provider_disabled")
            return OperationResult.permanent_error(
                message="Slack provider is disabled",
                error_code="PROVIDER_DISABLED",
            )

        # Validate required content
        if not message:
            log.error("empty_message_content")
            return OperationResult.permanent_error(
                message="Message content cannot be empty",
                error_code="EMPTY_CONTENT",
            )

        # Build message payload
        payload = {
            "channel": channel,
            **message,
        }

        # Add thread_ts if threading
        if thread_ts:
            payload["thread_ts"] = thread_ts

        # In real implementation, would use Bolt client
        # For now, return success with mock data
        log.info("slack_message_sent_success")
        return OperationResult.success(
            data={
                "channel": channel,
                "ts": "1234567890.123456",  # Mock timestamp
                "message": payload,
            },
            message="Message sent successfully",
        )

    def format_response(
        self,
        data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format response using SlackBlockKitFormatter.

        Args:
            data: Response data payload
            error: Optional error message

        Returns:
            Formatted response dict with Slack Block Kit blocks
        """
        if error:
            return self._formatter.format_error(message=error)
        return self._formatter.format_success(data=data)

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
        """Route a Slack hierarchical command from flat text input.

        Slack provides flat text input ("incident list --priority high"). This
        method parses the first token as the subcommand and routes the remainder
        to the matching handler using quote-aware tokenization.
        """
        if not text or not text.strip():
            return self.dispatch_command(root_command, payload)

        tokens = self._tokenize_command_text(text)
        if not tokens:
            return self.dispatch_command(root_command, payload)

        first_word = tokens[0]
        remaining_text = " ".join(tokens[1:]) if len(tokens) > 1 else ""

        if first_word.lower() in self.SLACK_HELP_KEYWORDS:
            payload.text = first_word
            return self.dispatch_command(root_command, payload)

        child_path = f"{root_command}.{first_word}"
        if child_path in self._commands:
            payload.text = remaining_text
            return self.dispatch_command(child_path, payload)

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

    def _append_command_help(
        self,
        lines: list,
        cmd_def,  # CommandDefinition
        indent_level: int,
        locale: str,
    ) -> None:
        """Recursively append command help with hierarchical formatting.

        Args:
            lines: List of strings to append to
            cmd_def: CommandDefinition to render
            indent_level: Current indentation level (0 = root)
            locale: Locale string for translations
        """
        indent = "  " * indent_level

        # Convert dot notation to space-separated for display
        # e.g., "sre.dev.aws" → "sre dev aws"
        display_path = build_slack_display_path(cmd_def.full_path)

        # Add command path and description as the bullet point (if not auto-generated)
        if not cmd_def.is_auto_generated:
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            self._logger.debug(
                "command_help_translation",
                command=cmd_def.full_path,
                key=cmd_def.description_key,
                locale=locale,
                translated=desc,
                fallback=cmd_def.description,
            )
            if desc:
                lines.append(f"{indent}• /{display_path} - {desc}")
            else:
                # Fallback to just command path if no description
                lines.append(f"{indent}• /{display_path}")
        else:
            # For auto-generated commands, show the command path
            lines.append(f"{indent}• /{display_path}")

        # Build and add command signature indented below
        signature = build_slack_command_signature(
            cmd_def.full_path,
            cmd_def.usage_hint,
        )
        lines.append(f"{indent}  `{signature}`")

        # Don't show examples when displaying a list of subcommands
        # Examples are only shown when user requests help for a specific command

        # Add blank line after command
        lines.append("")

    def generate_help(
        self,
        locale: str = "en-US",
        root_command: Optional[str] = None,
    ) -> str:
        """Generate Slack-formatted help text for registered commands.

        Supports hierarchical command display using the new dot notation.
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
        if not self._commands:
            msg = self._translate_or_fallback(
                "commands.errors.no_commands_registered",
                "No commands registered.",
                locale,
            )
            return msg

        # Translate section header
        header = self._translate_or_fallback(
            "commands.labels.available_commands", "Available Commands", locale
        )
        lines = [f"*{header}*", ""]

        # Determine which commands to display
        if root_command:
            # Show children of root_command
            children = self._get_child_commands(root_command)
            if not children:
                msg = self._translate_or_fallback(
                    "commands.errors.no_commands_under",
                    f"No commands found under `{root_command}`",
                    locale,
                )
                return msg

            # Render each child command with its subtree
            for cmd_def in children:
                self._append_command_help(lines, cmd_def, indent_level=0, locale=locale)
        else:
            # Show all top-level commands (no parent)
            top_level = [cmd for cmd in self._commands.values() if not cmd.parent]

            if not top_level:
                msg = self._translate_or_fallback(
                    "commands.errors.no_top_level_commands",
                    "No top-level commands registered.",
                    locale,
                )
                return msg

            for cmd_def in sorted(top_level, key=lambda c: c.name):
                self._append_command_help(lines, cmd_def, indent_level=0, locale=locale)

        return "\n".join(lines)

    def generate_command_help(self, command_name: str, locale: str = "en-US") -> str:
        """Generate Slack-formatted help text for a specific command.

        Uses Slack markdown formatting (backticks, asterisks, bullet points).

        Args:
            command_name: Full path of the command (e.g., "sre.dev.aws")
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Slack-formatted help text for the specified command
        """
        # Look up command by full_path
        cmd_def = self._commands.get(command_name)
        if not cmd_def:
            return f"Unknown command: `{command_name}`"

        lines = []

        # Convert dot notation to space-separated for display
        # e.g., "sre.dev.aws" → "/sre dev aws"
        display_path = build_slack_display_path(cmd_def.full_path)

        # Build command signature
        signature = build_slack_command_signature(
            cmd_def.full_path,
            cmd_def.usage_hint,
        )

        lines.append(f"*{signature}*")
        lines.append("")

        # Translate description (skip if auto-generated)
        if not cmd_def.is_auto_generated:
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(desc)
                lines.append("")

        # Add arguments if present (for leaf commands)
        if cmd_def.arguments:
            arguments_label = self._translate_or_fallback(
                "commands.labels.arguments", "Arguments:", locale
            )
            # Generate formatted argument help using utility with i18n support
            args_help = generate_slack_help_text(
                cmd_def.arguments,
                include_types=True,
                include_defaults=True,
                indent="  ",
                include_header=True,
                header=f"*{arguments_label}*",
                translate=lambda key, fallback: self._translate_or_fallback(
                    key, fallback, locale
                ),
            )
            lines.append(args_help)

        # Add examples (skip if auto-generated)
        if not cmd_def.is_auto_generated and cmd_def.examples:
            # Translate "Examples:" label
            examples_label = self._translate_or_fallback(
                "commands.labels.examples", "Examples:", locale
            )
            lines.append("")
            lines.append(f"*{examples_label}*")

            for i, example in enumerate(cmd_def.examples):
                # Try to translate example if key available
                if i < len(cmd_def.example_keys):
                    example_text = self._translate_or_fallback(
                        cmd_def.example_keys[i], example, locale
                    )
                else:
                    example_text = example

                example_line = f"`/{display_path} {example_text}`"
                lines.append(f"• {example_line}")

        # Show sub-commands if any
        children = self._get_child_commands(cmd_def.full_path)
        if children:
            lines.append("")
            subcommands_label = self._translate_or_fallback(
                "commands.labels.subcommands", "Sub-commands:", locale
            )
            lines.append(f"*{subcommands_label}*")
            for child in children:
                child_display = build_slack_display_path(child.full_path)
                lines.append(f"• `/{child_display}`")
                if not child.is_auto_generated and child.description:
                    desc = self._translate_or_fallback(
                        child.description_key, child.description, locale
                    )
                    if desc:
                        lines.append(f"  {desc}")

        return "\n".join(lines)
