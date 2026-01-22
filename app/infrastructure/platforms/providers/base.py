"""Base platform provider abstract class.

All platform-specific providers (Slack, Teams, Discord) inherit from this base class.
"""

import structlog
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import CapabilityDeclaration
from infrastructure.platforms.models import (
    CommandPayload,
    CommandResponse,
    CommandDefinition,
)
from infrastructure.platforms.parsing import (
    CommandArgumentParser,
    ArgumentParsingError,
)

from infrastructure.i18n.models import TranslationKey, Locale

if TYPE_CHECKING:
    from infrastructure.i18n.translator import Translator


logger = structlog.get_logger()


class BasePlatformProvider(ABC):
    """Abstract base class for all platform providers.

    Platform providers wrap collaboration platform SDKs (Slack Bolt, Teams Bot SDK, etc.)
    and provide a unified interface for sending messages, formatting responses, and
    declaring capabilities.

    All providers must:
    - Declare their capabilities via get_capabilities()
    - Implement send_message() for posting to the platform
    - Implement format_response() for converting data to platform-native format
    - Provide metadata (name, version, enabled status)

    Attributes:
        _name: Human-readable provider name (e.g., "Slack Provider").
        _version: Provider version string (e.g., "1.0.0").
        _enabled: Whether this provider is enabled in configuration.
    """

    def __init__(self, name: str, version: str = "1.0.0", enabled: bool = True):
        """Initialize the platform provider.

        Args:
            name: Human-readable provider name.
            version: Provider version string.
            enabled: Whether provider is enabled.
        """
        self._name = name
        self._version = version
        self._enabled = enabled
        self._logger = logger.bind(provider=name, version=version)
        # Commands stored by full_path (e.g., "sre.dev.aws") as key
        self._commands: Dict[str, CommandDefinition] = {}
        self._translator: Optional["Translator"] = None
        self._parent_command: Optional[str] = None  # e.g., "sre" for "/sre geolocate"

    @property
    def name(self) -> str:
        """Get the provider name."""
        return self._name

    @property
    def version(self) -> str:
        """Get the provider version."""
        return self._version

    @property
    def enabled(self) -> bool:
        """Check if the provider is enabled."""
        return self._enabled

    @abstractmethod
    def get_capabilities(self) -> CapabilityDeclaration:
        """Get the capability declaration for this provider.

        Returns:
            CapabilityDeclaration instance describing supported features.
        """
        pass

    @abstractmethod
    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send a message to the platform.

        Args:
            channel: Channel/conversation ID or user ID.
            message: Platform-specific message payload (Block Kit, Adaptive Card, etc.).
            thread_ts: Optional thread timestamp for threaded messages.

        Returns:
            OperationResult with message metadata on success, error on failure.
        """
        pass

    def initialize_app(self) -> OperationResult:
        """Initialize platform app (if needed).

        For platforms requiring app initialization (e.g., Slack Socket Mode),
        override this method to set up connections or event handlers.

        Default implementation does nothing.
        """
        return OperationResult.success(message="No app initialization needed")

    def get_webhook_router(self):
        """Get FastAPI router for HTTP webhooks.

        For HTTP-based platforms (Teams, Discord): Returns APIRouter with webhook endpoints.
        For WebSocket-based platforms (Slack Socket Mode): Returns None.

        Returns:
            Optional[APIRouter]: Router with webhook endpoints, or None if not HTTP-based.

        Example:
            # Teams/Discord provider (HTTP webhooks)
            router = provider.get_webhook_router()
            if router:
                app.include_router(router, prefix="/webhooks/teams")

            # Slack provider (WebSocket/Socket Mode)
            router = provider.get_webhook_router()
            assert router is None  # No webhooks needed
        """
        return None  # Default: no webhook router (WebSocket mode)

    @abstractmethod
    def format_response(
        self,
        data: Dict[str, Any],
        message_type: str = "success",
    ) -> Dict[str, Any]:
        """Format a response dict into platform-native format.

        Args:
            data: Data dictionary to format.
            message_type: Type of message ("success", "error", "info", "warning").

        Returns:
            Platform-specific message payload (Block Kit, Adaptive Card, Embed, etc.).
        """
        pass

    def supports_capability(self, capability: str) -> bool:
        """Check if this provider supports a specific capability.

        Args:
            capability: Capability identifier (from PlatformCapability enum).

        Returns:
            True if capability is supported, False otherwise.
        """
        capabilities = self.get_capabilities()
        return any(cap.value == capability for cap in capabilities.capabilities)

    def set_translator(self, translator: "Translator") -> None:
        """Set translator for i18n support in help generation.

        Args:
            translator: Translator instance for message translation
        """
        self._translator = translator

    def _translate_or_fallback(
        self,
        key: Optional[str],
        fallback: str,
        locale: str = "en-US",
    ) -> str:
        """Translate a key or return fallback if translation unavailable.

        Args:
            key: Translation key (e.g., "commands.geolocate.description")
            fallback: Fallback text if key is None or translation missing
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Translated text or fallback
        """
        if not key:
            return fallback

        if not self._translator:
            # No translator configured, use fallback
            self._logger.debug(
                "translation_skipped_no_translator",
                key=key,
                locale=locale,
            )
            return fallback

        try:
            # Create TranslationKey from dot-separated string
            translation_key = TranslationKey.from_string(key)

            # Convert locale string to Locale enum
            locale_enum = Locale.from_string(locale)

            # Attempt translation
            result = self._translator.translate_message(
                translation_key, locale_enum, variables=None
            )

            # Return translation if successful, otherwise fallback
            translated = result if result else fallback
            self._logger.debug(
                "translation_result",
                key=key,
                locale=locale,
                found=bool(result),
                result=translated,
            )
            return translated

        except Exception as e:
            self._logger.warning(
                "translation_failed",
                key=key,
                locale=locale,
                error=str(e),
            )
            return fallback

    def _ensure_parent_chain_exists(self, parent: str) -> None:
        """Ensure all intermediate parent nodes exist in the command tree.

        Auto-generates intermediate command nodes if they don't exist.

        Args:
            parent: Parent command path in dot notation (e.g., "sre.dev" creates "sre" and "sre.dev" nodes)

        Example:
            # Registering command with parent="sre.dev" ensures:
            # 1. "sre" node exists (auto-generated if needed)
            # 2. "sre.dev" node exists (auto-generated if needed)
            # 3. Then registers the actual command as child of "sre.dev"
        """
        if not parent:
            return

        # Split parent chain: "sre.dev" -> ["sre", "dev"]
        parts = parent.split(".")

        # Build intermediate paths: ["sre", "sre.dev"]
        for i in range(len(parts)):
            partial_path = ".".join(parts[: i + 1])

            # Create auto-generated node if doesn't exist
            if partial_path not in self._commands:
                # Determine parent for this node
                node_parent = ".".join(parts[:i]) if i > 0 else None
                node_name = parts[i]
                auto_cmd = CommandDefinition(
                    name=node_name,
                    handler=None,  # No handler for auto-generated nodes
                    description=f"Commands for {node_name}",  # Generic description
                    parent=node_parent,
                    is_auto_generated=True,
                )

                self._commands[partial_path] = auto_cmd

                self._logger.debug(
                    "auto_generated_intermediate_command",
                    path=partial_path,
                    parent=node_parent,
                )

    def _get_child_commands(self, parent_path: str) -> List[CommandDefinition]:
        """Get all direct children of a command node.

        Args:
            parent_path: Parent full_path (e.g., "sre.dev")

        Returns:
            List of child CommandDefinition objects
        """
        children = []
        for cmd in self._commands.values():
            # Check if this command's parent matches
            if cmd.parent == parent_path:
                children.append(cmd)

        return sorted(children, key=lambda c: c.name)

    def set_parent_command(self, parent: str) -> None:
        """Set parent command prefix for help generation.

        DEPRECATED: This method is being phased out. Use the `parent` parameter
        in register_command() instead.

        Args:
            parent: Parent command (e.g., "sre" for "/sre geolocate")
        """
        self._parent_command = parent

    @abstractmethod
    def get_user_locale(self, user_id: str) -> str:
        """Get user's locale from platform API.

        Platform-specific providers must implement this to extract
        the user's locale from their respective APIs (Slack, Teams, Discord).

        Args:
            user_id: Platform-specific user ID

        Returns:
            Locale string (e.g., "en-US", "fr-FR"), defaults to "en-US" on error
        """
        pass

    @abstractmethod
    def generate_help(
        self, locale: str = "en-US", root_command: Optional[str] = None
    ) -> str:
        """Generate formatted help text for registered commands.

        Platform-specific implementation with appropriate formatting
        (Slack: `/command`, Teams: `@BotName command`, Discord: `/command`).

        Supports hierarchical command display:
        - If root_command is None: Shows all top-level commands
        - If root_command is specified: Shows only children of that command

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")
            root_command: Optional root command full_path (e.g., "sre.dev")
                         to filter help to only its children

        Returns:
            Formatted help text with commands and examples

        Example Output (Slack):
            ```
            Available commands:
            • `/sre` - SRE Operations
            • `/sre dev` - Development tools
            • `/sre dev aws` - AWS development commands
            ```
        """
        pass

    @abstractmethod
    def generate_command_help(self, command_name: str, locale: str = "en-US") -> str:
        """Generate formatted help text for a specific command.

        Platform-specific implementation with appropriate formatting
        (Slack markdown, Teams Adaptive Cards, Discord embeds, etc.).

        Args:
            command_name: Full path of the command (e.g., "sre.dev.aws")
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Formatted help text for the specified command
        """
        pass

    def dispatch_command(
        self, command_name: str, payload: CommandPayload
    ) -> CommandResponse:
        """Dispatch a command to its registered handler.

        Args:
            command_name: Name of the command to dispatch
            payload: CommandPayload with command text and metadata

        Returns:
            CommandResponse from the handler, or error response if command not found

        Raises:
            None - always returns CommandResponse (no exceptions)
        """
        # Look up command first
        cmd_def = self._commands.get(command_name)
        if not cmd_def:
            return CommandResponse(
                message=f"Unknown command: {command_name}",
                ephemeral=True,
            )

        # Enrich payload with user locale if not already set
        # This ensures platform-specific locale extraction happens automatically
        if not payload.user_locale or payload.user_locale == "en-US":
            # Try to get actual user locale from platform API
            try:
                detected_locale = self.get_user_locale(payload.user_id)
                if detected_locale and detected_locale != "en-US":
                    payload.user_locale = detected_locale
                    self._logger.info(
                        "locale_enriched_from_platform",
                        user_id=payload.user_id,
                        locale=detected_locale,
                    )
            except Exception as e:
                self._logger.warning(
                    "locale_enrichment_failed",
                    user_id=payload.user_id,
                    error=str(e),
                )

        # Get user's locale for help/error messages
        user_locale = payload.user_locale
        self._logger.debug(
            "dispatch_command_locale",
            command=command_name,
            locale=user_locale,
        )

        # Check for EXPLICIT help requests (unless in legacy mode)
        # Legacy mode allows the handler to process help itself
        text = payload.text.strip().lower() if payload.text else ""
        if not cmd_def.legacy_mode and text in ("help", "aide", "--help", "-h"):
            # Return help for this specific command only
            help_text = self.generate_command_help(command_name, locale=user_locale)
            return CommandResponse(message=help_text, ephemeral=True)

        # If command has no handler (auto-generated parent), show help for children
        # This handles cases like `/sre dev` where `dev` is just a grouping node
        if cmd_def.handler is None:
            help_text = self.generate_help(
                locale=user_locale, root_command=command_name
            )
            return CommandResponse(message=help_text, ephemeral=True)

        # Dispatch to handler
        try:
            # Parse arguments if defined
            parsed_args = None
            request = None

            if cmd_def.arguments:
                # If command expects arguments but none provided
                if not payload.text or not payload.text.strip():
                    # Use fallback handler if provided, otherwise show help
                    if cmd_def.fallback_handler:
                        return cmd_def.fallback_handler(payload)
                    else:
                        help_text = self.generate_command_help(
                            command_name, locale=user_locale
                        )
                        return CommandResponse(message=help_text, ephemeral=True)

                parser = CommandArgumentParser(cmd_def.arguments)
                try:
                    parsed_args = parser.parse(payload.text)

                    # Apply argument mapper if provided
                    if cmd_def.argument_mapper:
                        mapped_args = cmd_def.argument_mapper(parsed_args)
                    else:
                        mapped_args = parsed_args

                    # Validate with schema if provided
                    if cmd_def.schema:
                        request = cmd_def.schema(**mapped_args)

                except ArgumentParsingError as e:
                    # Show parsing errors (invalid arguments, unknown options, etc.)
                    return CommandResponse(
                        message=f"❌ Argument parsing error: {e.message}",
                        ephemeral=True,
                    )
                except Exception as e:
                    return CommandResponse(
                        message=f"❌ Validation error: {str(e)}",
                        ephemeral=True,
                    )

            # Call handler with appropriate arguments
            if request is not None:
                # Handler expects: payload, parsed_args, request
                response = cmd_def.handler(payload, parsed_args, request)
            elif parsed_args is not None:
                # Handler expects: payload, parsed_args
                response = cmd_def.handler(payload, parsed_args)
            else:
                # Handler expects: payload only
                response = cmd_def.handler(payload)

            return response
        except Exception as e:
            self._logger.error(
                "command_handler_error",
                command=command_name,
                error=str(e),
            )
            return CommandResponse(
                message=f"Error executing {command_name}: {str(e)}",
                ephemeral=True,
            )

    def __repr__(self) -> str:
        """String representation of the provider."""
        return (
            f"{self.__class__.__name__}("
            f"name={self._name!r}, "
            f"version={self._version!r}, "
            f"enabled={self._enabled})"
        )
