"""Microsoft Teams platform provider.

HTTP-based platform provider for Microsoft Teams Bot Framework integration.

Connection Mode: HTTP (Webhook-based)
- Teams sends events via HTTP POST to webhook endpoints
- No persistent WebSocket connection required
- Signature verification for security

Example:
    >>> from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    >>> from infrastructure.configuration.infrastructure.platforms import TeamsPlatformSettings
    >>>
    >>> settings = TeamsPlatformSettings(
    ...     ENABLED=True,
    ...     APP_ID="your-app-id",
    ...     APP_PASSWORD="your-app-password"
    ... )
    >>> provider = TeamsPlatformProvider(settings=settings)
    >>> caps = provider.get_capabilities()
    >>> caps.connection_mode
    'http'
"""

import structlog
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter
from infrastructure.platforms.models import CommandDefinition
from infrastructure.platforms.providers.base import BasePlatformProvider

logger = structlog.get_logger()


class TeamsPlatformProvider(BasePlatformProvider):
    """Microsoft Teams platform provider with HTTP webhook support.

    Provides Teams Bot Framework integration via HTTP webhooks. Unlike Slack's
    Socket Mode, Teams uses standard HTTP POST webhooks for all bot interactions.

    Key Features:
    - HTTP webhook-based communication (no WebSocket)
    - Bot Framework SDK compatibility
    - Adaptive Cards formatting
    - Task modules and messaging extensions
    - Activity-based event handling

    Attributes:
        _settings: Teams platform configuration
        _formatter: TeamsAdaptiveCardsFormatter for response formatting
        _app_initialized: Whether Bot Framework app has been configured

    Example:
        >>> provider = TeamsPlatformProvider(settings=teams_settings)
        >>> result = provider.send_message(
        ...     channel="19:meeting_thread_id",
        ...     message={"text": "Hello Teams!"}
        ... )
        >>> if result.is_success:
        ...     print("Message sent successfully")
    """

    def __init__(
        self,
        settings,  # TeamsPlatformSettings type
        formatter: Optional[TeamsAdaptiveCardsFormatter] = None,
        name: str = "teams",
        version: str = "1.0.0",
    ):
        """Initialize Teams platform provider.

        Args:
            settings: TeamsPlatformSettings instance with app credentials and config
            formatter: Optional TeamsAdaptiveCardsFormatter for response formatting
            name: Provider name (default: "teams")
            version: Provider version (default: "1.0.0")
        """
        super().__init__(
            name=name,
            version=version,
            enabled=settings.ENABLED,
        )

        self._settings = settings
        self._formatter = formatter or TeamsAdaptiveCardsFormatter()

        # Will be initialized when app is started
        self._app = None
        self._adapter = None
        self._app_initialized = False

        self._logger.info(
            "teams_provider_initialized",
            connection_mode="http",
            enabled=settings.ENABLED,
        )

    def get_capabilities(self) -> CapabilityDeclaration:
        """Get Teams platform capabilities.

        Returns:
            CapabilityDeclaration with supported Teams capabilities
        """
        return create_capability_declaration(
            "teams",
            PlatformCapability.COMMANDS,
            PlatformCapability.INTERACTIVE_CARDS,
            PlatformCapability.VIEWS_MODALS,
            PlatformCapability.FILE_SHARING,
            PlatformCapability.REACTIONS,
            metadata={
                "connection_mode": "http",
                "platform": "teams",
                "framework": "botframework",
            },
        )

    def get_webhook_router(self):
        """Get FastAPI router for Teams HTTP webhooks.

        Teams uses HTTP webhooks for all bot interactions. This method returns
        a FastAPI APIRouter with endpoints for receiving Teams activities.

        Returns:
            Optional[APIRouter]: Router with webhook endpoints, or None if not initialized.

        Note:
            This is a placeholder. Full implementation would include:
            - POST /messages - Receive messages/activities from Teams
            - POST /messaging - Handle messaging extension queries
            - Signature verification middleware
            - Activity handler registration

        Example:
            >>> router = provider.get_webhook_router()
            >>> if router:
            ...     app.include_router(router, prefix="/webhooks/teams")
        """
        # TODO: Implement Teams webhook router with Bot Framework endpoints
        # from fastapi import APIRouter
        # router = APIRouter()
        # @router.post("/messages")
        # def handle_teams_activity(request: Request): ...
        # return router
        self._logger.warning(
            "teams_webhook_router_not_implemented",
            message="Teams webhook router is a placeholder - requires Bot Framework integration",
        )
        return None  # Placeholder - to be implemented with Bot Framework SDK

    def get_user_locale(self, user_id: str) -> str:
        """Get user's locale from Teams API.

        Args:
            user_id: Teams user ID

        Returns:
            Locale string, defaults to "en-US"

        Note:
            TODO: Implement Teams-specific locale extraction using Bot Framework SDK.
            Teams user locale can be extracted from:
            - Activity.locale property in incoming messages
            - User profile via Microsoft Graph API
        """
        # TODO: Implement Teams locale extraction
        return "en-US"

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send a message to a Teams channel or chat.

        Args:
            channel: Teams conversation/channel ID (e.g., "19:meeting_id@thread.v2")
            message: Message payload (Adaptive Card or text)
            thread_ts: Optional reply-to message ID (not commonly used in Teams)

        Returns:
            OperationResult with send status

        Example:
            >>> result = provider.send_message(
            ...     channel="19:meeting_id@thread.v2",
            ...     message={"text": "Hello!", "attachments": [...]}
            ... )
        """
        log = self._logger.bind(channel=channel, has_thread=bool(thread_ts))
        log.info("sending_teams_message")

        if not self.enabled:
            log.warning("teams_provider_disabled")
            return OperationResult.permanent_error(
                message="Teams provider is disabled",
                error_code="PROVIDER_DISABLED",
            )

        # Validate message
        if not message:
            log.error("empty_message_provided")
            return OperationResult.permanent_error(
                message="Message cannot be empty",
                error_code="INVALID_MESSAGE",
            )

        log.debug("preparing_teams_message")

        # Build Teams activity payload
        payload: dict[str, Any] = {
            "type": "message",
            "conversation": {"id": channel},
        }

        # Merge message content (Adaptive Card or simple text)
        payload.update(message)

        # Add reply-to reference if provided (optional in Teams)
        if thread_ts:
            payload["replyToId"] = thread_ts

        log.info(
            "teams_message_prepared",
            channel=channel,
            has_attachments="attachments" in message,
        )

        # In real implementation, this would call Bot Framework Connector API
        # For now, return success to indicate message was formatted correctly
        return OperationResult.success(
            message="Message formatted for Teams",
            data={"channel": channel, "payload": payload},
        )

    def format_response(
        self,
        data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format response using TeamsAdaptiveCardsFormatter.

        Args:
            data: Response data payload
            error: Optional error message

        Returns:
            Formatted response dict with Teams Adaptive Card
        """
        if error:
            return self._formatter.format_error(message=error)
        return self._formatter.format_success(data=data)

    def initialize_app(self) -> OperationResult:
        """Initialize Teams Bot Framework application.

        For HTTP mode, this validates configuration but doesn't establish
        a persistent connection (unlike Slack Socket Mode).

        Returns:
            OperationResult indicating initialization status

        Example:
            >>> result = provider.initialize_app()
            >>> if result.is_success:
            ...     print("Teams app configured")
        """
        log = self._logger.bind(connection_mode="http")
        log.info("initializing_teams_app")

        if not self._settings.ENABLED:
            log.warning("teams_disabled_skipping_init")
            return OperationResult.success(
                message="Teams provider disabled, skipping initialization"
            )

        # Validate required credentials
        if not self._settings.APP_ID:
            log.error("missing_app_id")
            return OperationResult.permanent_error(
                message="APP_ID is required",
                error_code="MISSING_APP_ID",
            )

        if not self._settings.APP_PASSWORD:
            log.error("missing_app_password")
            return OperationResult.permanent_error(
                message="APP_PASSWORD is required",
                error_code="MISSING_APP_PASSWORD",
            )

        # TODO: Initialize Bot Framework Adapter when ready
        # from botbuilder.core import BotFrameworkAdapter
        # from botbuilder.schema import Activity
        #
        # self._adapter = BotFrameworkAdapter(
        #     app_id=self._settings.APP_ID,
        #     app_password=self._settings.APP_PASSWORD
        # )

        self._app_initialized = True

        log.info("teams_app_initialized_placeholder")
        return OperationResult.success(
            data={"initialized": True, "connection_mode": "http"},
            message="Teams app initialization completed (placeholder)",
        )

    @property
    def formatter(self) -> TeamsAdaptiveCardsFormatter:
        """Get the Teams Adaptive Cards formatter.

        Returns:
            TeamsAdaptiveCardsFormatter instance
        """
        return self._formatter

    @property
    def settings(self):
        """Get Teams platform settings.

        Returns:
            TeamsPlatformSettings instance
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
    ) -> None:
        """Register a Teams command with hierarchical support.

        Automatically creates intermediate command nodes if parent uses dot notation.

        Note: Teams uses @mention syntax, not slash commands: "@BotName command args"

        Args:
            command: Command name (e.g., "aws", "test-connection")
            handler: Function that handles CommandPayload → CommandResponse
            description: English description (fallback if translation unavailable)
            description_key: i18n translation key (e.g., "commands.aws.description")
            usage_hint: Usage string (e.g., "<account_id>")
            examples: List of example argument strings
            example_keys: List of translation keys for examples
            parent: Dot notation parent path (e.g., "sre.dev")

        Example:
            # Register nested command: @BotName sre dev aws test-connection
            provider.register_command(
                command="test-connection",
                handler=handle_test_connection,
                description="Test AWS connection",
                parent="sre.dev.aws",
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
        )

        # Store by full_path
        self._commands[cmd_def.full_path] = cmd_def

        self._logger.debug(
            "teams_command_registered",
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
        """Recursively append command help with hierarchical formatting for Teams.

        Args:
            lines: List of strings to append to
            cmd_def: CommandDefinition to render
            indent_level: Current indentation level (0 = root)
            locale: Locale string for translations
        """
        indent = "  " * indent_level

        # Convert dot notation to space-separated for display
        # e.g., "sre.dev.aws" → "@BotName sre dev aws"
        display_path = cmd_def.full_path.replace(".", " ")
        bot_name = getattr(self._settings, "BOT_NAME", "SREBot")

        # Build command signature (Teams uses @mention, not slash)
        if cmd_def.usage_hint:
            signature = f"@{bot_name} {display_path} {cmd_def.usage_hint}"
        else:
            signature = f"@{bot_name} {display_path}"

        # Add command line (Teams markdown uses ** for bold)
        lines.append(f"{indent}• **{signature}**")

        # Add description if not auto-generated
        if not cmd_def.is_auto_generated:
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"{indent}  {desc}")

        # Add examples if not auto-generated
        if not cmd_def.is_auto_generated and cmd_def.examples:
            examples_label = self._translate_or_fallback(
                "commands.labels.examples", "Examples:", locale
            )
            lines.append(f"{indent}  **{examples_label}**")

            for i, example in enumerate(cmd_def.examples):
                # Try to translate example if key available
                if i < len(cmd_def.example_keys):
                    example_text = self._translate_or_fallback(
                        cmd_def.example_keys[i], example, locale
                    )
                else:
                    example_text = example

                example_line = f"`@{bot_name} {display_path} {example_text}`"
                lines.append(f"{indent}    • {example_line}")

        # Add blank line after command
        lines.append("")

    def generate_help(
        self,
        locale: str = "en-US",
        root_command: Optional[str] = None,
    ) -> str:
        """Generate Teams-formatted help text for registered commands.

        Supports hierarchical command display using the new dot notation.
        Uses Teams markdown formatting (** for bold).

        Note: Teams uses @mention syntax, not slash commands.

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")
            root_command: Optional root command full_path (e.g., "sre.dev")
                         to filter help to only its children. If None, shows
                         all top-level commands.

        Returns:
            Teams-formatted help text with commands and examples

        Example Output:
            ```
            **Available Commands**

            • **@SREBot sre** - SRE Operations
            • **@SREBot sre dev** - Development tools
              • **@SREBot sre dev aws** - AWS development commands
            ```
        """
        if not self._commands:
            return "No commands registered."

        lines = ["**Available Commands**", ""]

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

        """Generate Teams-formatted help text for all registered commands.

        TODO: Implement with Adaptive Cards formatting for rich help display.
        Current implementation uses plain text as placeholder.

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Teams-formatted help text (currently plain text)
        """
        if not self._commands:
            return "No commands registered."

        prefix = self._parent_command if self._parent_command else ""
        lines = ["**Commands**", ""]

        for cmd_def in self._commands.values():
            # Build command signature
            prefix_str = f"/{prefix} {cmd_def.name}" if prefix else f"/{cmd_def.name}"
            if cmd_def.usage_hint:
                signature = f"{prefix_str} {cmd_def.usage_hint}"
            else:
                signature = prefix_str
            lines.append(f"**{signature}**")

            # Translate description
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"  {desc}")

            # Add examples
            if cmd_def.examples:
                examples_label = self._translate_or_fallback(
                    "commands.labels.examples", "Examples:", locale
                )
                lines.append(f"  **{examples_label}**")

                for i, example in enumerate(cmd_def.examples):
                    if i < len(cmd_def.example_keys):
                        example_text = self._translate_or_fallback(
                            cmd_def.example_keys[i], example, locale
                        )
                    else:
                        example_text = example

                    example_line = (
                        f"`/{prefix} {cmd_def.name} {example_text}`"
                        if prefix
                        else f"`/{cmd_def.name} {example_text}`"
                    )
                    lines.append(f"  • {example_line}")

            lines.append("")

        return "\n".join(lines)

    def generate_command_help(self, command_name: str, locale: str = "en-US") -> str:
        """Generate Teams-formatted help text for a specific command.

        Uses Teams markdown formatting (** for bold).
        Note: Teams uses @mention syntax, not slash commands.

        Args:
            command_name: Full path of the command (e.g., "sre.dev.aws")
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Teams-formatted help text for the specified command
        """
        # Look up command by full_path
        cmd_def = self._commands.get(command_name)
        if not cmd_def:
            return f"Unknown command: `{command_name}`"

        lines = []

        # Convert dot notation to space-separated for display
        # e.g., "sre.dev.aws" → "@SREBot sre dev aws"
        display_path = cmd_def.full_path.replace(".", " ")
        bot_name = getattr(self._settings, "BOT_NAME", "SREBot")

        # Build command signature (Teams uses @mention, not slash)
        if cmd_def.usage_hint:
            signature = f"@{bot_name} {display_path} {cmd_def.usage_hint}"
        else:
            signature = f"@{bot_name} {display_path}"

        lines.append(f"**{signature}**")
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
            lines.append(f"**{examples_label}**")

            for i, example in enumerate(cmd_def.examples):
                # Try to translate example if key available
                if i < len(cmd_def.example_keys):
                    example_text = self._translate_or_fallback(
                        cmd_def.example_keys[i], example, locale
                    )
                else:
                    example_text = example

                example_line = f"`@{bot_name} {display_path} {example_text}`"
                lines.append(f"• {example_line}")

        # Show sub-commands if any
        children = self._get_child_commands(cmd_def.full_path)
        if children:
            lines.append("")
            lines.append("**Sub-commands:**")
            for child in children:
                child_display = child.full_path.replace(".", " ")
                lines.append(f"• **@{bot_name} {child_display}**")
                if not child.is_auto_generated and child.description:
                    desc = self._translate_or_fallback(
                        child.description_key, child.description, locale
                    )
                    if desc:
                        lines.append(f"  {desc}")

        return "\n".join(lines)
