"""Slack-specific command adapter implementation."""

from typing import Any, Callable, Dict

from core.logging import get_module_logger
from infrastructure.commands.adapters.base import CommandAdapter
from infrastructure.commands.context import CommandContext, ResponseChannel

logger = get_module_logger()


class SlackResponseChannel(ResponseChannel):
    """Slack-specific response channel implementation."""

    def __init__(
        self,
        respond: Callable,
        client: Any,
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


class SlackCommandAdapter(CommandAdapter):
    """Adapter for Slack Bolt SDK.

    Bridges Slack-specific command handling to platform-agnostic framework.

    Example::

        from infrastructure.commands import CommandRegistry, SlackCommandAdapter
        from infrastructure.i18n import Translator, LocaleResolver

        registry = CommandRegistry("groups")
        translator = Translator()
        locale_resolver = LocaleResolver()

        adapter = SlackCommandAdapter(
            registry=registry,
            translator=translator,
            locale_resolver=locale_resolver,
        )

        bot.command("/sre groups")(adapter.handle)
    """

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
        client = platform_payload.get("client")
        respond = platform_payload.get("respond")
        body = platform_payload.get("body", {})

        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")

        # Get user email
        user_email = ""
        try:
            if client:
                user_info = client.users_info(user=user_id)
                if user_info.get("ok"):
                    user_email = (
                        user_info.get("user", {}).get("profile", {}).get("email", "")
                    )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("failed_to_get_user_email", user_id=user_id, error=str(e))

        # Resolve locale
        locale = "en-US"  # Default
        if self.locale_resolver:
            try:
                locale_ctx = self.locale_resolver.from_slack(
                    client, {"user_id": user_id}
                )
                locale = locale_ctx.locale.value
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "failed_to_resolve_locale", user_id=user_id, error=str(e)
                )

        # Create response channel
        if respond is None or client is None:
            # Fallback if critical data is missing - create no-op responder
            def noop_respond(**kwargs):  # pylint: disable=unused-argument
                pass

            if respond is None:
                respond = noop_respond
            if client is None:
                client = None  # type: ignore

        responder = SlackResponseChannel(respond, client, channel_id, user_id)

        # Create context
        ctx = CommandContext(
            platform="slack",
            user_id=user_id,
            user_email=user_email,
            channel_id=channel_id,
            locale=locale,
            metadata={
                "user_name": command.get("user_name", ""),
                "team_id": command.get("team_id", ""),
                "trigger_id": body.get("trigger_id", ""),
                "slack_client": client,
            },
        )
        ctx._responder = responder  # pylint: disable=protected-access
        ctx._translator = self.translator  # pylint: disable=protected-access

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

    def handle(  # pylint: disable=arguments-differ
        self, ack=None, command=None, client=None, respond=None, body=None
    ):  # type: ignore
        """Handle Slack command (supports both old and new signatures).

        Supports legacy signature:
            adapter.handle(ack, command, client, respond)

        And new signature:
            adapter.handle({"ack": ack, "command": command, ...})

        Args:
            ack: Slack acknowledgment function (legacy)
            command: Slack command dict (legacy)
            client: Slack client (legacy)
            respond: Slack respond function (legacy)
            body: Slack body dict (legacy)
        """
        # Support legacy signature
        if ack is not None and not isinstance(ack, dict):
            platform_payload = {
                "ack": ack,
                "command": command,
                "client": client,
                "respond": respond,
                "body": body or {},
            }
        else:
            # New signature: first arg is payload dict
            platform_payload = ack if isinstance(ack, dict) else {}

        # Call base class handle
        super().handle(platform_payload)
