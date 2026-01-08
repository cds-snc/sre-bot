"""Slack-specific command adapter implementation - simplified and DRY."""

import re
from typing import Any, Callable, Dict, Optional
from slack_sdk import WebClient

import structlog

from infrastructure.commands.providers.base import CommandProvider
from infrastructure.commands.context import CommandContext, ResponseChannel
from infrastructure.commands.providers import register_command_provider
from infrastructure.commands.responses.slack_formatter import SlackResponseFormatter
from infrastructure.i18n.models import TranslationKey, Locale
from infrastructure.services.providers import get_translation_service
from integrations.slack.users import get_user_email_from_id, get_user_email_from_handle

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

logger = structlog.get_logger()


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
        self.respond(**self.formatter.format_card(card), **kwargs)

    def send_error(self, error: Any, **kwargs) -> None:
        """Send error message.

        Args:
            error: ErrorMessage object from infrastructure.commands.responses.models
            **kwargs: Additional Slack-specific options
        """
        self.respond(**self.formatter.format_error(error), **kwargs)

    def send_success(self, success: Any, **kwargs) -> None:
        """Send success message.

        Args:
            success: SuccessMessage object from infrastructure.commands.responses.models
            **kwargs: Additional Slack-specific options
        """
        self.respond(**self.formatter.format_success(success), **kwargs)


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

    def __init__(self, settings: "Settings", config: Dict[str, Any]):
        """Initialize Slack adapter.

        Args:
            settings: Settings instance (required for dependency injection)
            config: Provider configuration dict from settings.commands.providers['slack']

        Raises:
            ValueError: If SLACK_TOKEN is not configured
        """

        self.settings = settings

        # Validate Slack is configured
        if not self.settings.slack.SLACK_TOKEN:
            raise ValueError("SLACK_TOKEN required for Slack command provider")

        # NOTE: Registry, translator, and locale_resolver are set later by modules
        # This allows each module to attach its own command registry and i18n context
        translation_service = get_translation_service()
        super().__init__(
            registry=None,  # Will be set by modules
            translator=translation_service.translator,  # Access underlying Translator
            locale_resolver=None,  # Will be set in create_context
        )

        self.config = config

    def _resolve_framework_locale(self, platform_payload: Any) -> str:
        """Resolve locale for framework operations (help, errors).

        Quick locale resolution using Slack user profile.

        Args:
            platform_payload: Slack command payload

        Returns:
            Locale string (e.g., "en-US", "fr-FR")
        """
        try:
            command = platform_payload.get("command", {})
            client: WebClient | None = platform_payload.get("client")
            user_id = command.get("user_id", "")

            if client and user_id:
                user_info = client.users_info(user=user_id, include_locale=True)
                if user_info.get("ok"):
                    return user_info["user"].get("locale", "en-US")
            elif self.locale_resolver:
                return self.locale_resolver.default_locale.value
        except Exception as e:  # pylint: disable=broad-except
            logger.debug(
                "failed_to_resolve_framework_locale", error=str(e), fallback="en-US"
            )
        return "en-US"

    def extract_command_text(self, platform_payload: Any) -> str:
        """Extract command text from Slack command payload.

        Args:
            platform_payload: Dict with keys: ack, command, client, respond

        Returns:
            Command text without slash command prefix
        """
        command = platform_payload.get("command", {})
        return command.get("text", "").strip()

    def _preprocess_users(self, platform_payload: Any, text: str) -> str:
        """Resolve Slack user mentions to email addresses in text.

        Handles multiple mention formats:
        - Escaped: <@U012ABCDEF> or <@U012ABCDEF|alice>
        - Plain text: @alice
        - In flags: --user=@alice or --user=<@U012ABCDEF>

        Args:
            platform_payload: Slack payload with client
            text: Text potentially containing user mentions

        Returns:
            Text with mentions resolved to emails (or left unchanged if unresolvable)
        """

        client: WebClient | None = platform_payload.get("client")
        if not client:
            logger.warning("preprocess_users_no_client")
            return text

        # Pattern 1: Escaped mentions <@U12345> or <@U12345|name>
        def resolve_escaped_mention(match):
            user_id = match.group(1).split("|")[0]  # Extract ID before pipe if present
            email = get_user_email_from_id(client, user_id)
            if email:
                logger.debug("resolved_escaped_mention", user_id=user_id, email=email)
                return email
            # Graceful fallback: leave unchanged
            logger.debug("unresolved_escaped_mention", user_id=user_id)
            return match.group(0)

        text = re.sub(r"<@([A-Z0-9|]+)>", resolve_escaped_mention, text)

        # Pattern 2: Plain text handles @alice (but not emails like alice@example.com)
        def resolve_plain_mention(match):
            handle = match.group(1)
            email = get_user_email_from_handle(client, handle)
            if email:
                logger.debug("resolved_plain_mention", handle=handle, email=email)
                return email
            # Graceful fallback: leave unchanged (might be @my_awesome_word)
            logger.debug("unresolved_plain_mention", handle=handle)
            return match.group(0)

        # Match @handle but NOT email addresses (negative lookbehind for alphanumeric before @)
        # and NOT if already followed by domain pattern
        text = re.sub(
            r"(?<![a-zA-Z0-9])@([a-zA-Z0-9._-]+)(?!@|\.[a-zA-Z]{2,})",
            resolve_plain_mention,
            text,
        )

        return text

    def _preprocess_channels(self, platform_payload: Any, text: str) -> str:
        """Resolve Slack channel mentions to channel IDs in text.

        Handles multiple mention formats:
        - Escaped: <#C012ABCDEF|channel-name>
        - Plain text: #channel-name
        - In flags: --channel=#general or --channel=<#C012ABCDEF|general>

        Args:
            platform_payload: Slack payload with client
            text: Text potentially containing channel mentions

        Returns:
            Text with mentions resolved to channel IDs (or left unchanged if unresolvable)
        """
        client: WebClient | None = platform_payload.get("client")
        if not client:
            logger.warning("preprocess_channels_no_client")
            return text

        # Pattern 1: Escaped mentions <#C12345|name> (already contains ID)
        def resolve_escaped_channel(match):
            channel_id = match.group(1).split("|")[0]  # Extract ID before pipe
            logger.debug("resolved_escaped_channel", channel_id=channel_id)
            return channel_id

        text = re.sub(r"<#([A-Z0-9|]+)>", resolve_escaped_channel, text)

        # Pattern 2: Plain text #channel-name
        def resolve_plain_channel(match):
            channel_name = match.group(1)
            # Try to resolve via conversations.list
            try:
                channels = client.conversations_list(types="public_channel", limit=100)
                if channels.get("ok"):
                    for channel in channels.get("channels", []):
                        if channel.get("name") == channel_name:
                            channel_id = channel["id"]
                            logger.debug(
                                "resolved_plain_channel",
                                channel_name=channel_name,
                                channel_id=channel_id,
                            )
                            return channel_id
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "resolve_plain_channel_failed",
                    channel_name=channel_name,
                    error=str(e),
                )

            # Graceful fallback: leave unchanged
            logger.debug("unresolved_plain_channel", channel_name=channel_name)
            return match.group(0)

        text = re.sub(r"#([a-z0-9_-]+)", resolve_plain_channel, text)

        return text

    def preprocess_command_text(self, platform_payload: Any, text: str) -> str:
        """Preprocess Slack command text to resolve mentions and channels.

        Transforms:
        - @username → user@example.com (via Slack API)
        - <@U12345> → user@example.com (via Slack API)
        - #channel-name → C12345 (via Slack API)
        - <#C12345|channel> → C12345 (extracted)
        - Unresolvable mentions → left unchanged (graceful fallback)

        Args:
            platform_payload: Slack payload with client
            text: Raw command text

        Returns:
            Text with Slack identifiers resolved where possible
        """
        text = self._preprocess_users(platform_payload, text)
        text = self._preprocess_channels(platform_payload, text)
        return text

    def _make_translator_callable(self) -> Optional[Callable]:
        """Create a callable wrapper for translator.translate_message.

        Returns a function that accepts string keys and locale strings,
        converting them to TranslationKey/Locale enums before calling translator.

        Returns:
            Translator callable or None if no translator is set
        """
        if self.translator is None:
            return None

        translator = self.translator

        def translate_fn(key_str: str, locale_str: str, **variables) -> str:
            """Translate a string key with variables."""
            try:
                translation_key = TranslationKey.from_string(key_str)
                locale_enum = (
                    Locale.from_string(locale_str)
                    if isinstance(locale_str, str)
                    else locale_str
                )
                return translator.translate_message(
                    translation_key, locale_enum, variables=variables
                )
            except Exception:  # pylint: disable=broad-except
                return key_str  # Fallback to key if translation fails

        return translate_fn

    def create_context(self, platform_payload: Any) -> CommandContext:
        """Create CommandContext from Slack command payload.

        Extracts Slack-specific fields (user, channel, locale, client) and populates
        CommandContext with minimal Slack metadata (client, respond, command).

        Args:
            platform_payload: Dict with keys: ack, command, client, respond

        Returns:
            CommandContext with Slack-specific settings
        """
        command = platform_payload.get("command", {})
        client: WebClient | None = platform_payload.get("client")
        respond = platform_payload.get("respond")

        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")

        # Get user email
        user_email = ""
        try:
            if client and user_id:
                user_email = get_user_email_from_id(client, user_id) or ""
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("failed_to_get_user_email", user_id=user_id, error=str(e))

        # Resolve locale
        locale = self._resolve_framework_locale(platform_payload)

        # Validate required dependencies
        if client is None:
            raise ValueError("Slack client required for command execution")
        if respond is None:
            raise ValueError("Respond function required for command execution")

        # Create response channel
        responder = SlackResponseChannel(respond, client, channel_id, user_id)

        # Create context with clean Slack metadata pattern
        ctx = CommandContext(
            platform="slack",
            user_id=user_id,
            user_email=user_email,
            channel_id=channel_id,
            locale=locale,
            metadata={
                "client": client,
                "respond": respond,
                "command": command,
            },
        )
        ctx.set_responder(responder)
        translator_fn = self._make_translator_callable()
        if translator_fn:
            ctx.set_translator(translator_fn)
        return ctx

    def _validate_payload(self, platform_payload) -> None:
        """Validate Slack command payload structure.
        Args:
            platform_payload: Payload to validate
        Raises:
            ValueError: If payload is invalid
        """
        if not isinstance(platform_payload, dict):
            logger.error(
                "invalid_slack_payload_type",
                payload_type=type(platform_payload).__name__,
            )
            raise ValueError(
                f"Expected dict payload, got {type(platform_payload).__name__}"
            )

        required_fields = {"ack", "command", "client", "respond"}
        missing = required_fields - set(platform_payload.keys())
        if missing:
            logger.error("slack_payload_missing_fields", missing_fields=missing)
            raise ValueError(f"Slack payload missing required fields: {missing}")

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

    def send_help(self, platform_payload: Any, help_text: str) -> None:
        """Send help text to Slack channel.

        Args:
            platform_payload: Dict with "respond" function
            help_text: Help text to display
        """
        respond = platform_payload.get("respond")
        if respond:
            respond(text=help_text)
