"""Base platform provider abstract class.

All platform-specific providers (Slack, Teams, Discord) inherit from this base class.
"""

import structlog
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import CapabilityDeclaration
from infrastructure.platforms.models import (
    CommandPayload,
    CommandResponse,
    CommandDefinition,
)

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

    def set_parent_command(self, parent: str) -> None:
        """Set parent command prefix for help generation.

        Args:
            parent: Parent command (e.g., "sre" for "/sre geolocate")
        """
        self._parent_command = parent

    def register_command(
        self,
        command: str,
        handler: Callable[[CommandPayload], CommandResponse],
        description: str = "",
        description_key: Optional[str] = None,
        usage_hint: str = "",
        examples: Optional[List[str]] = None,
        example_keys: Optional[List[str]] = None,
    ) -> None:
        """Register a platform command with metadata for auto-help generation.

        Args:
            command: Command name (e.g., "geolocate" or "/geolocate")
            handler: Function that handles CommandPayload → CommandResponse
            description: English description (fallback if translation unavailable)
            description_key: i18n translation key (e.g., "geolocate.slack.description")
            usage_hint: Usage string (e.g., "<ip_address>")
            examples: List of example argument strings (not full command)
            example_keys: List of translation keys for examples

        Example:
            provider.register_command(
                command="geolocate",
                handler=handle_geolocate_command,
                description="Lookup geographic location of an IP address",
                description_key="geolocate.slack.description",
                usage_hint="<ip_address>",
                examples=["8.8.8.8", "1.1.1.1"],
            )
        """
        # Normalize command name (remove leading slash if present)
        cmd_name = command.lstrip("/")

        self._commands[cmd_name] = CommandDefinition(
            name=cmd_name,
            handler=handler,
            description=description,
            description_key=description_key,
            usage_hint=usage_hint,
            examples=examples or [],
            example_keys=example_keys or [],
        )

        self._logger.debug(
            "command_registered",
            command=cmd_name,
            has_description=bool(description or description_key),
        )

    def generate_help(self, locale: str = "en-US") -> str:
        """Generate formatted help text for all registered commands.

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Formatted help text with all registered commands and examples
        """
        if not self._commands:
            return "No commands registered."

        prefix = self._parent_command if self._parent_command else ""
        lines = ["*Commands*", ""]

        for cmd_def in self._commands.values():
            # Build command signature
            prefix_str = f"/{prefix} {cmd_def.name}" if prefix else f"/{cmd_def.name}"
            if cmd_def.usage_hint:
                signature = f"{prefix_str} {cmd_def.usage_hint}"
            else:
                signature = prefix_str
            lines.append(f"`{signature}`")

            # Translate description
            desc = self._translate_or_fallback(
                cmd_def.description_key, cmd_def.description, locale
            )
            if desc:
                lines.append(f"  {desc}")

            # Add examples
            if cmd_def.examples:
                # Translate "Examples:" label
                examples_label = self._translate_or_fallback(
                    "commands.labels.examples", "Examples:", locale
                )
                lines.append(f"  *{examples_label}*")

                for i, example in enumerate(cmd_def.examples):
                    # Try to translate example if key available
                    if i < len(cmd_def.example_keys):
                        example_text = self._translate_or_fallback(
                            cmd_def.example_keys[i], example, locale
                        )
                    else:
                        example_text = example

                    example_line = (
                        f"`{prefix} {cmd_def.name} {example_text}`"
                        if prefix
                        else f"/{cmd_def.name} {example_text}`"
                    )
                    lines.append(f"  • {example_line}")

            lines.append("")  # Blank line between commands

        return "\n".join(lines)

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
        # Check for help requests
        text = payload.text.strip().lower() if payload.text else ""
        if not text or text in ("help", "aide", "--help", "-h"):
            # Return help as a response
            help_text = self.generate_help()
            return CommandResponse(message=help_text, ephemeral=True)

        # Look up command
        cmd_def = self._commands.get(command_name)
        if not cmd_def:
            return CommandResponse(
                message=f"Unknown command: {command_name}",
                ephemeral=True,
            )

        # Dispatch to handler
        try:
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

    def _translate_or_fallback(
        self, key: Optional[str], fallback: str, locale: str
    ) -> str:
        """Translate key or return fallback text.

        Args:
            key: Translation key (e.g., "geolocate.slack.description")
            fallback: Fallback text if translation unavailable
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Translated message or fallback text
        """
        if not key or not self._translator:
            return fallback

        try:
            from infrastructure.i18n.models import TranslationKey, Locale

            translation_key = TranslationKey.from_string(key)
            locale_enum = Locale.from_string(locale)
            translated = self._translator.translate_message(
                translation_key, locale_enum
            )
            return translated if translated else fallback
        except Exception as e:
            self._logger.debug(
                "translation_fallback",
                key=key,
                error=str(e),
                locale=locale,
            )
            return fallback

    def __repr__(self) -> str:
        """String representation of the provider."""
        return (
            f"{self.__class__.__name__}("
            f"name={self._name!r}, "
            f"version={self._version!r}, "
            f"enabled={self._enabled})"
        )
