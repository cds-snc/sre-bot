"""Slack-specific command adapter implementation."""

from typing import Any, Callable, Dict, Protocol
from slack_sdk import WebClient

from core.config import settings
from core.logging import get_module_logger
from infrastructure.commands.providers.base import CommandProvider
from infrastructure.commands.context import CommandContext, ResponseChannel
from infrastructure.commands.providers import register_command_provider
from infrastructure.commands.responses.slack_formatter import SlackResponseFormatter
from infrastructure.i18n.models import TranslationKey, Locale
from integrations.slack import users as slack_users

logger = get_module_logger()


class SlackPayload(Protocol):
    """Protocol defining the structure of a Slack command payload.

    This protocol documents the expected structure passed by Slack Bolt SDK
    when handling slash commands. It ensures type safety and clarity for
    what the SlackCommandProvider expects.

    Attributes:
        ack: Function to acknowledge command receipt (required within 3 seconds)
        command: Dict with Slack command metadata (user_id, channel_id, text, etc.)
        client: WebClient instance for making Slack API calls
        respond: Function to send a response message to the user
        body: Full request body (contains trigger_id, team_id, etc.)
    """

    ack: Callable[[], None]
    command: Dict[str, Any]
    client: WebClient
    respond: Callable[..., Any]
    body: Dict[str, Any]


class SlackResponseChannel(ResponseChannel):
    """Slack-specific response channel implementation."""

    def __init__(
        self,
        respond: Callable,
        client: WebClient,
        channel_id: str,
        user_id: str,
    ):
        """Initialize Slack responder.

        Args:
            respond: Slack respond function
            client: Slack client
            channel_id: Channel ID for ephemeral messages
            user_id: User ID for ephemeral messages
        """
        self.respond = respond
        self.client = client
        self.channel_id = channel_id
        self.user_id = user_id
        self.formatter = SlackResponseFormatter()

    def send_message(self, text: str, **kwargs) -> None:
        """Send public message visible to all in channel."""
        self.respond(text=text, **kwargs)

    def send_ephemeral(self, text: str, **kwargs) -> None:
        """Send ephemeral message visible only to user."""
        self.client.chat_postEphemeral(
            channel=self.channel_id,
            user=self.user_id,
            text=text,
            **kwargs,
        )

    def send_card(self, card: Any, **kwargs) -> None:
        """Send rich card message.

        Args:
            card: Card object from infrastructure.commands.responses.models
            **kwargs: Additional Slack-specific options
        """
        formatted = self.formatter.format_card(card)
        self.respond(**formatted, **kwargs)

    def send_error(self, error: Any, **kwargs) -> None:
        """Send error message.

        Args:
            error: ErrorMessage object from infrastructure.commands.responses.models
            **kwargs: Additional Slack-specific options
        """
        formatted = self.formatter.format_error(error)
        self.respond(**formatted, **kwargs)

    def send_success(self, success: Any, **kwargs) -> None:
        """Send success message.

        Args:
            success: SuccessMessage object from infrastructure.commands.responses.models
            **kwargs: Additional Slack-specific options
        """
        formatted = self.formatter.format_success(success)
        self.respond(**formatted, **kwargs)


@register_command_provider("slack")
class SlackCommandProvider(CommandProvider):
    """Adapter for Slack Bolt SDK.

    Bridges Slack-specific command handling to platform-agnostic framework.
    Registered as 'slack' command provider.

    Example::

        from infrastructure.commands.providers import get_provider

        adapter = get_provider('slack')
        adapter.registry = my_registry
        bot.command("/sre groups")(adapter.handle)
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Slack adapter.

        Args:
            config: Provider configuration dict from settings.commands.providers['slack']

        Raises:
            ValueError: If SLACK_TOKEN is not configured
        """
        # pylint: disable=import-outside-toplevel

        # Validate Slack is configured
        if not settings.slack.SLACK_TOKEN:
            raise ValueError("SLACK_TOKEN required for Slack command provider")

        # NOTE: Registry, translator, and locale_resolver are set later by modules
        # This allows each module to attach its own command registry and i18n context
        super().__init__(
            registry=None,  # Will be set by modules
            translator=None,  # Will be set in create_context from LocaleResolver
            locale_resolver=None,  # Will be set in create_context
        )

        self.config = config

    def _resolve_user_locale(self, client: WebClient | None, user_id: str) -> Locale:
        """Resolve user's locale from Slack profile or fall back to defaults.

        Tries in order:
        1. Slack user profile locale (requires client and user_id)
        2. Resolver default (if configured)
        3. EN_US fallback

        Args:
            client: Slack WebClient or None
            user_id: Slack user ID

        Returns:
            Resolved Locale enum
        """
        try:
            if client and user_id:
                # Use Slack-specific locale resolution
                locale_str = slack_users.get_user_locale(client, user_id)
                locale_enum = Locale.from_string(locale_str)
                logger.info(
                    "resolved_slack_user_locale",
                    user_id=user_id,
                    locale=locale_enum.value,
                )
                return locale_enum
            elif self.locale_resolver:
                # Fallback to resolver if no Slack client
                return self.locale_resolver.default_locale
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "failed_to_resolve_user_locale",
                user_id=user_id,
                error=str(e),
                fallback_locale=Locale.EN_US.value,
            )
        return Locale.EN_US

    def extract_command_text(self, platform_payload: Dict[str, Any]) -> str:
        """Extract command text from Slack command payload.

        Args:
            platform_payload: Dict with keys: ack, command, client, respond, body

        Returns:
            Command text without slash command prefix
        """
        command = platform_payload.get("command", {})
        return command.get("text", "").strip()

    def create_context(self, platform_payload: Dict[str, Any]) -> CommandContext:
        """Create CommandContext from Slack command payload.

        Args:
            platform_payload: Dict with keys: ack, command, client, respond, body

        Returns:
            CommandContext with Slack-specific settings
        """
        command = platform_payload.get("command", {})
        client: WebClient | None = platform_payload.get("client")
        respond = platform_payload.get("respond")
        body = platform_payload.get("body", {})

        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")

        # Get user email
        user_email = ""
        try:
            if client:
                user_email = slack_users.get_user_email_from_body(client, body)

        except Exception as e:  # pylint: disable=broad-except
            logger.warning("failed_to_get_user_email", user_id=user_id, error=str(e))

        # Resolve locale
        locale_enum = self._resolve_user_locale(client, user_id)

        # Validate required dependencies for response channel
        if client is None:
            logger.error(
                "slack_client_missing",
                user_id=user_id,
                error="Cannot create response channel without Slack client",
            )
            raise ValueError("Slack client required for command execution")

        if respond is None:
            logger.error(
                "slack_respond_missing",
                user_id=user_id,
                error="Cannot create response channel without respond function",
            )
            raise ValueError("Respond function required for command execution")

        # Create response channel with validated dependencies
        responder = SlackResponseChannel(respond, client, channel_id, user_id)

        # Create context
        ctx = CommandContext(
            platform="slack",
            user_id=user_id,
            user_email=user_email,
            channel_id=channel_id,
            locale=locale_enum.value,
            metadata={
                "user_name": command.get("user_name", ""),
                "team_id": command.get("team_id", ""),
                "trigger_id": body.get("trigger_id", ""),
                "slack_client": client,
            },
        )
        ctx._responder = responder  # pylint: disable=protected-access
        # Set translator callable - wrap translate_message to handle string keys and locales
        translator = self.translator
        if translator is not None:

            def translate_fn(
                key_str: str, locale_str, **variables
            ):  # pylint: disable=unused-argument
                """Translate a string key to a TranslationKey and translate."""
                try:
                    translation_key = TranslationKey.from_string(key_str)
                    # Convert locale string to Locale enum if needed
                    if isinstance(locale_str, str):
                        locale_enum = Locale.from_string(locale_str)
                    else:
                        locale_enum = locale_str
                    return translator.translate_message(
                        translation_key, locale_enum, variables=variables
                    )
                except Exception:  # pylint: disable=broad-except
                    return key_str  # Fallback to key if translation fails

            ctx._translator = translate_fn  # pylint: disable=protected-access
        else:
            ctx._translator = None  # pylint: disable=protected-access

        return ctx

    def acknowledge(self, platform_payload: Dict[str, Any]) -> None:
        """Acknowledge Slack command immediately (< 3 seconds required).

        Args:
            platform_payload: Dict with "ack" function
        """
        ack = platform_payload.get("ack")
        if ack:
            ack()

    def send_error(self, platform_payload: Dict[str, Any], message: str) -> None:
        """Send error message to Slack channel.

        Args:
            platform_payload: Dict with "respond" function
            message: Error message text
        """
        respond = platform_payload.get("respond")
        if respond:
            respond(text=f":x: {message}")

    def send_help(self, platform_payload: Dict[str, Any], help_text: str) -> None:
        """Send help text to Slack channel.

        Args:
            platform_payload: Dict with "respond" function
            help_text: Help text to display
        """
        respond = platform_payload.get("respond")
        if respond:
            respond(text=help_text)

    def handle(self, platform_payload: Any) -> None:
        """Handle Slack command with proper payload validation.

        Accepts a SlackPayload dict with keys: ack, command, client, respond, body.

        Args:
            platform_payload: Dict matching SlackPayload protocol with Slack command data

        Raises:
            ValueError: If required fields are missing from payload
        """
        # Validate and parse payload
        if not isinstance(platform_payload, dict):
            logger.error(
                "invalid_slack_payload_type",
                payload_type=type(platform_payload).__name__,
            )
            raise ValueError(
                f"Expected dict payload, got {type(platform_payload).__name__}"
            )

        required_fields = {"ack", "command", "client", "respond", "body"}
        missing = required_fields - set(platform_payload.keys())
        if missing:
            logger.error("slack_payload_missing_fields", missing_fields=missing)
            raise ValueError(f"Slack payload missing required fields: {missing}")

        # Call base class handle with validated payload
        super().handle(platform_payload)
