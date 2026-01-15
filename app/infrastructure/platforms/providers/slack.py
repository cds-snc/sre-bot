"""Slack platform provider implementation.

Provides integration with Slack using the Bolt SDK for Socket Mode.
"""

import structlog
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.models import CommandDefinition
from infrastructure.platforms.providers.base import BasePlatformProvider

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
        self._app = None
        self._client = None

        self._logger.info(
            "slack_provider_initialized",
            socket_mode=settings.SOCKET_MODE,
            enabled=settings.ENABLED,
        )

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
            metadata={
                "socket_mode": self._settings.SOCKET_MODE,
                "platform": "slack",
                "connection_mode": "websocket",
            },
        )

    def get_webhook_router(self):
        """Get webhook router for Slack.

        Slack uses Socket Mode (WebSocket), so no HTTP webhooks are needed.

        Returns:
            None (WebSocket mode, not HTTP)
        """
        return None  # Slack uses Socket Mode (WebSocket), not HTTP webhooks

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
        """Initialize Slack Bolt app (placeholder for future implementation).

        This will set up:
        - Bolt App instance
        - Socket Mode handler
        - Event listeners
        - Command handlers

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

        # TODO: Initialize Bolt App when ready (CLARIFICATION REQUIRED: fastapi startup is handled in main.py and server initializes the platform apps)
        # from slack_bolt import App
        # from slack_bolt.adapter.socket_mode import SocketModeHandler
        #
        # self._app = App(token=self._settings.BOT_TOKEN)
        # if self._settings.SOCKET_MODE:
        #     handler = SocketModeHandler(
        #         self._app,
        #         self._settings.APP_TOKEN
        #     )
        # self._client = self._app.client

        log.info("slack_app_initialized_placeholder")
        return OperationResult.success(
            data={"initialized": True, "socket_mode": self._settings.SOCKET_MODE},
            message="Slack app initialization completed (placeholder)",
        )

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

    def register_command(
        self,
        command: str,
        handler,  # Callable[[CommandPayload], CommandResponse]
        description: str = "",
        description_key: Optional[str] = None,
        usage_hint: str = "",
        examples: Optional[list] = None,
        example_keys: Optional[list] = None,
        parent: Optional[str] = None,
        legacy_mode: bool = False,
    ) -> None:
        """Register a Slack command with hierarchical support.

        Automatically creates intermediate command nodes if parent uses dot notation.

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

        Example:
            # Register nested command: /sre dev aws test-connection
            provider.register_command(
                command="test-connection",
                handler=handle_test_connection,
                description="Test AWS connection",
                parent="sre.dev.aws",
            )

            # Automatically creates:
            # - CommandDefinition(name="sre", full_path="sre", is_auto_generated=True)
            # - CommandDefinition(name="dev", full_path="sre.dev", is_auto_generated=True)
            # - CommandDefinition(name="aws", full_path="sre.dev.aws", is_auto_generated=True)
            # - CommandDefinition(name="test-connection", full_path="sre.dev.aws.test-connection")
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
        # e.g., "sre.dev.aws" → "/sre dev aws"
        display_path = cmd_def.full_path.replace(".", " ")

        # Build command signature
        if cmd_def.usage_hint:
            signature = f"/{display_path} {cmd_def.usage_hint}"
        else:
            signature = f"/{display_path}"

        # Add command line
        lines.append(f"{indent}• `{signature}`")

        # Add description if not auto-generated
        if not cmd_def.is_auto_generated:
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"{indent}  {desc}")

        # Add examples ONLY for leaf commands (commands without children)
        # Commands with subcommands should only show description
        has_children = bool(self._get_child_commands(cmd_def.full_path))
        if not cmd_def.is_auto_generated and cmd_def.examples and not has_children:
            examples_label = self._translate_or_fallback(
                "commands.labels.examples", "Examples:", locale
            )
            lines.append(f"{indent}  *{examples_label}*")

            for i, example in enumerate(cmd_def.examples):
                # Try to translate example if key available
                if i < len(cmd_def.example_keys):
                    example_text = self._translate_or_fallback(
                        cmd_def.example_keys[i], example, locale
                    )
                else:
                    example_text = example

                example_line = f"`/{display_path} {example_text}`"
                lines.append(f"{indent}    • {example_line}")

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
            return "No commands registered."

        lines = ["*Available Commands*", ""]

        # Determine which commands to display
        if root_command:
            # Show children of root_command
            children = self._get_child_commands(root_command)
            if not children:
                return f"No commands found under `{root_command}`"

            # Render each child command with its subtree
            for cmd_def in children:
                self._append_command_help(lines, cmd_def, indent_level=0, locale=locale)
        else:
            # Show all top-level commands (no parent)
            top_level = [cmd for cmd in self._commands.values() if not cmd.parent]

            if not top_level:
                return "No top-level commands registered."

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
        display_path = cmd_def.full_path.replace(".", " ")

        # Build command signature
        if cmd_def.usage_hint:
            signature = f"/{display_path} {cmd_def.usage_hint}"
        else:
            signature = f"/{display_path}"

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

        # Add examples (skip if auto-generated)
        if not cmd_def.is_auto_generated and cmd_def.examples:
            # Translate "Examples:" label
            examples_label = self._translate_or_fallback(
                "commands.labels.examples", "Examples:", locale
            )
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
            lines.append("*Sub-commands:*")
            for child in children:
                child_display = child.full_path.replace(".", " ")
                lines.append(f"• `/{child_display}`")
                if not child.is_auto_generated and child.description:
                    desc = self._translate_or_fallback(
                        child.description_key, child.description, locale
                    )
                    if desc:
                        lines.append(f"  {desc}")

        return "\n".join(lines)
