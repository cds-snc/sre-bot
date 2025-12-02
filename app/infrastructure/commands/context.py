"""Command execution context - platform agnostic."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol
from uuid import uuid4

from core.logging import get_module_logger

logger = get_module_logger()


class ResponseChannel(Protocol):
    """Protocol for platform-specific response channels."""

    def send_message(self, text: str, **kwargs) -> None:
        """Send message to user."""
        ...  # pylint: disable=unnecessary-ellipsis

    def send_ephemeral(self, text: str, **kwargs) -> None:
        """Send ephemeral message (visible only to user)."""
        ...  # pylint: disable=unnecessary-ellipsis

    def send_card(self, card: Any, **kwargs) -> None:
        """Send rich card/embed message.

        Args:
            card: Card object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        ...  # pylint: disable=unnecessary-ellipsis

    def send_error(self, error: Any, **kwargs) -> None:
        """Send error message.

        Args:
            error: ErrorMessage object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        ...  # pylint: disable=unnecessary-ellipsis

    def send_success(self, success: Any, **kwargs) -> None:
        """Send success message.

        Args:
            success: SuccessMessage object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        ...  # pylint: disable=unnecessary-ellipsis


@dataclass
class CommandContext:
    """Platform-agnostic command execution context.

    Provides unified interface for handlers regardless of platform (Slack, Teams, API).
    Integrates with localization system for translated responses.

    Attributes:
        platform: Platform name (slack, teams, api)
        user_id: Platform-specific requestor user identifier
        user_email: User's email address of the requestor (considered universal ID across platforms)
        channel_id: Platform-specific channel identifier
        locale: User's preferred locale (e.g., en-US, fr-FR)
        metadata: Platform-specific metadata (e.g., Slack command payload)
        translator: Translation function (injected by adapter)
        responder: Response channel (injected by adapter)

    Example:
        def handle_command(ctx: CommandContext, arg1: str):
            # Translate message
            msg = ctx.translate("groups.success.add", member_email=arg1)
            ctx.respond(msg)
            ctx.respond_ephemeral(ctx.translate("groups.help.hint"))
    """

    platform: str
    user_id: str
    user_email: str
    channel_id: str
    locale: str = "en-US"
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    # Injected by adapter
    _translator: Optional[Any] = field(default=None)  # Callable[[str, str, ...], str]
    _responder: Optional[ResponseChannel] = field(default=None)

    def __post_init__(self):
        """Initialize defaults."""
        if self.metadata is None:
            self.metadata = {}
        if self.correlation_id is None:
            self.correlation_id = str(uuid4())

    def translate(self, key: str, **variables) -> str:
        """Translate message with user's locale.

        Args:
            key: Translation key (e.g., "groups.success.add")
            **variables: Variables for interpolation

        Returns:
            Translated message string or key if translator not set

        Raises:
            ValueError: If translator not set via adapter
        """
        if self._translator is None:
            logger.warning("translate called without translator set", key=key)
            return key
        return self._translator(key, self.locale, **variables)

    def respond(self, text: str, **kwargs) -> None:
        """Send response message to user.

        Args:
            text: Message text
            **kwargs: Platform-specific options

        Raises:
            ValueError: If responder not set via adapter
        """
        if self._responder is None:
            logger.warning("respond called without responder set", text=text)
            return
        self._responder.send_message(text, **kwargs)

    def respond_ephemeral(self, text: str, **kwargs) -> None:
        """Send ephemeral message (visible only to user).

        Args:
            text: Message text
            **kwargs: Platform-specific options

        Raises:
            ValueError: If responder not set via adapter
        """
        if self._responder is None:
            logger.warning("respond_ephemeral called without responder set", text=text)
            return
        self._responder.send_ephemeral(text, **kwargs)

    def respond_card(self, card: Any, **kwargs) -> None:
        """Send rich card response.

        Args:
            card: Card object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        if self._responder is None:
            logger.warning("respond_card called without responder set")
            return
        self._responder.send_card(card, **kwargs)

    def respond_error(self, error: Any, **kwargs) -> None:
        """Send error response.

        Args:
            error: ErrorMessage object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        if self._responder is None:
            logger.warning("respond_error called without responder set")
            return
        self._responder.send_error(error, **kwargs)

    def respond_success(self, success: Any, **kwargs) -> None:
        """Send success response.

        Args:
            success: SuccessMessage object from infrastructure.commands.responses.models
            **kwargs: Platform-specific options
        """
        if self._responder is None:
            logger.warning("respond_success called without responder set")
            return
        self._responder.send_success(success, **kwargs)

    def set_translator(self, translator: Callable) -> None:
        """Set the translator callable."""
        self._translator = translator

    def set_responder(self, responder: ResponseChannel) -> None:
        """Set the response channel."""
        self._responder = responder
