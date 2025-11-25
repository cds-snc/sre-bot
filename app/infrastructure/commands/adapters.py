"""Platform-specific adapters for command framework."""

from typing import Callable, Dict, Any, Optional

from core.logging import get_module_logger
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.parser import CommandParser, CommandParseError
from infrastructure.commands.context import CommandContext

logger = get_module_logger()


class SlackResponseChannel:
    """Slack-specific response channel."""

    def __init__(self, respond: Callable, client: Any, channel_id: str, user_id: str):
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
        """Send public message."""
        self.respond(text=text, **kwargs)

    def send_ephemeral(self, text: str, **kwargs) -> None:
        """Send ephemeral message (only visible to user)."""
        self.client.chat_postEphemeral(
            channel=self.channel_id, user=self.user_id, text=text, **kwargs
        )


class SlackCommandAdapter:
    """Adapter for Slack Bolt SDK.

    Bridges Slack-specific command handling to platform-agnostic framework.

    Example:
        from infrastructure.commands import CommandRegistry, SlackCommandAdapter

        registry = CommandRegistry("groups")

        @registry.command(name="list")
        def list_groups(ctx: CommandContext):
            ctx.respond("Groups: ...")

        adapter = SlackCommandAdapter(registry)
        bot.command("/sre groups")(adapter.handle)
    """

    def __init__(
        self,
        registry: CommandRegistry,
        translator: Optional[Callable[[str, str, Dict], str]] = None,
    ):
        """Initialize adapter.

        Args:
            registry: CommandRegistry with commands to dispatch
            translator: Optional translation function
        """
        self.registry = registry
        self.translator = translator
        self.parser = CommandParser()

    def handle(self, ack, command: Dict[str, Any], client: Any, respond: Callable):
        """Handle Slack slash command.

        Acknowledges immediately, parses command, creates context,
        and dispatches to registered handler.

        Args:
            ack: Slack acknowledgment function
            command: Slack command dict
            client: Slack client
            respond: Slack respond function
        """
        ack()

        try:
            text = command.get("text", "").strip()
            tokens = self._tokenize(text) if text else []

            if not tokens or tokens[0] in ("help", "aide", "--help", "-h"):
                self._send_help(respond)
                return

            # Parse command
            cmd_name = tokens[0]
            cmd = self.registry.get_command(cmd_name)

            if cmd is None:
                respond(
                    text=f":x: Unknown command: `{cmd_name}`. Type `help` for usage."
                )
                return

            # Create context
            ctx = self._create_context(command, client, respond)

            # Parse and execute
            arg_tokens = tokens[1:]
            parsed = self.parser.parse(cmd, arg_tokens)

            # Call handler
            cmd.handler(ctx, **parsed.args)

        except CommandParseError as e:
            respond(text=f":x: {str(e)}")
            logger.warning("command parse error", error=str(e), command=command)
        except Exception as e:
            respond(text=":x: An error occurred processing your command.")
            logger.exception("unhandled command error", error=str(e), command=command)

    def _tokenize(self, text: str) -> list:
        """Tokenize command text (respects quotes).

        Args:
            text: Command text from user

        Returns:
            List of tokens, respecting quoted strings
        """
        tokens = []
        current = []
        in_quote = None

        for char in text:
            if char in ('"', "'") and in_quote is None:
                in_quote = char
            elif char == in_quote:
                in_quote = None
                tokens.append("".join(current))
                current = []
            elif char == " " and in_quote is None:
                if current:
                    tokens.append("".join(current))
                    current = []
            else:
                current.append(char)

        if current:
            tokens.append("".join(current))

        return tokens

    def _create_context(
        self, command: Dict[str, Any], client: Any, respond: Callable
    ) -> CommandContext:
        """Create CommandContext from Slack command.

        Args:
            command: Slack command dict
            client: Slack client
            respond: Slack respond function

        Returns:
            CommandContext with Slack-specific settings
        """
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")

        # Get user email
        user_email = ""
        try:
            user_info = client.users_info(user=user_id)
            if user_info.get("ok"):
                user_email = (
                    user_info.get("user", {}).get("profile", {}).get("email", "")
                )
        except Exception as e:
            logger.warning("failed to get user email", user_id=user_id, error=str(e))

        # Create response channel
        responder = SlackResponseChannel(respond, client, channel_id, user_id)

        # Create context
        ctx = CommandContext(
            platform="slack",
            user_id=user_id,
            user_email=user_email,
            channel_id=channel_id,
        )
        ctx._responder = responder
        ctx._translator = self.translator

        return ctx

    def _send_help(self, respond: Callable):
        """Send help text.

        Args:
            respond: Slack respond function
        """
        help_text = self._generate_help()
        respond(text=help_text)

    def _generate_help(self) -> str:
        """Generate help text from registry.

        Returns:
            Formatted help text
        """
        lines = [f"*{self.registry.namespace.upper()} Commands*"]

        for cmd in self.registry.list_commands():
            lines.append(f"\n*/{self.registry.namespace} {cmd.name}*")

            if cmd.description:
                lines.append(f"  {cmd.description}")

            if cmd.args:
                for arg in cmd.args:
                    if arg.flag:
                        lines.append(f"  `{arg.name}` - {arg.description}")
                    else:
                        req = "required" if arg.required else "optional"
                        lines.append(f"  `{arg.name}` ({req}) - {arg.description}")

            if cmd.examples:
                lines.append("  Examples:")
                for example in cmd.examples:
                    lines.append(f"    `/{self.registry.namespace} {example}`")

            if cmd.subcommands:
                lines.append("  Subcommands:")
                for subcmd in cmd.subcommands.values():
                    lines.append(f"    `{subcmd.name}` - {subcmd.description}")

        return "\n".join(lines)
