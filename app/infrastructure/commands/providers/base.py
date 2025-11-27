"""Base provider for platform-agnostic command handling.

IMPORTANT: Modules MUST attach their registry before any commands are handled.

Example:
    # App startup (main.py or initialization code)
    from infrastructure.commands.providers import activate_providers
    providers = activate_providers()  # SlackCommandProvider instantiated, registry=None
    slack = providers["slack"]

    # Module initialization (modules/groups/groups.py or similar)
    from infrastructure.commands import CommandRegistry
    registry = CommandRegistry("groups")
    slack.registry = registry  # Attach registry

    # Command handling (when user sends /sre groups list)
    slack.handle(payload)  # Uses attached groups registry
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from core.logging import get_module_logger
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.parser import CommandParser, CommandParseError
from infrastructure.commands.context import CommandContext
from infrastructure.i18n.translator import Translator
from infrastructure.i18n.resolvers import LocaleResolver

logger = get_module_logger()


class CommandProvider(ABC):
    """Base class for platform-specific command providers.

    Implements generic command routing, parsing, and execution flow.
    Subclasses provide platform-specific context creation and acknowledgment.

    Example:
        class SlackCommandProvider(CommandProvider):
            def extract_command_text(self, platform_payload):
                return platform_payload["command"].get("text", "")

            def create_context(self, platform_payload):
                # Slack-specific context creation
                return CommandContext(...)
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        translator: Optional[Translator] = None,
        locale_resolver: Optional[LocaleResolver] = None,
    ):
        """Initialize provider with command registry.

        Args:
            registry: Optional CommandRegistry with commands to dispatch
            translator: Optional Translator instance for i18n
            locale_resolver: Optional LocaleResolver instance
        """
        self.registry = registry
        self.translator = translator
        self.locale_resolver = locale_resolver
        self.parser = CommandParser()

    def _ensure_registry(self) -> CommandRegistry:
        """Ensure registry is set, raise clear error if not.

        Returns:
            CommandRegistry instance

        Raises:
            RuntimeError: If registry not attached
        """
        if self.registry is None:
            raise RuntimeError(
                f"{self.__class__.__name__} registry not attached. "
                "Modules must call provider.registry = CommandRegistry(...) during startup."
            )
        return self.registry

    @abstractmethod
    def extract_command_text(self, platform_payload: Any) -> str:
        """Extract command text from platform-specific payload.

        Args:
            platform_payload: Platform-specific command data structure

        Returns:
            Command text string (without command prefix)
        """
        ...  # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def create_context(self, platform_payload: Any) -> CommandContext:
        """Create CommandContext from platform-specific payload.

        Must set up:
        - User identification (user_id, user_email)
        - Locale for i18n
        - Platform-specific metadata
        - Response channel (ctx._responder)
        - Translator (ctx._translator)

        Args:
            platform_payload: Platform-specific command data structure

        Returns:
            CommandContext ready for handler execution
        """
        ...  # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def acknowledge(self, platform_payload: Any) -> None:
        """Acknowledge command receipt (platform-specific).

        Some platforms (Slack) require immediate acknowledgment within 3s.
        Others (Teams) use different interaction models.

        Args:
            platform_payload: Platform-specific command data structure
        """
        ...  # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def send_error(self, platform_payload: Any, message: str) -> None:
        """Send error message to user (platform-specific).

        Args:
            platform_payload: Platform-specific command data structure
            message: Error message text
        """
        ...  # pylint: disable=unnecessary-ellipsis

    @abstractmethod
    def send_help(self, platform_payload: Any, help_text: str) -> None:
        """Send help text to user (platform-specific).

        Args:
            platform_payload: Platform-specific command data structure
            help_text: Help text to display
        """
        ...  # pylint: disable=unnecessary-ellipsis

    def handle(self, platform_payload: Any) -> None:
        """Handle command execution (generic flow).

        This method implements the common command handling logic:
        1. Acknowledge command
        2. Extract and tokenize command text
        3. Handle help requests
        4. Parse command and arguments
        5. Create execution context
        6. Execute handler
        7. Handle errors

        Args:
            platform_payload: Platform-specific command data structure
        """
        # Step 1: Acknowledge immediately (platform-specific)
        self.acknowledge(platform_payload)

        try:
            # Step 2: Extract command text (platform-specific)
            text = self.extract_command_text(platform_payload)
            tokens = self._tokenize(text) if text else []

            # Step 3: Handle help requests
            if not tokens or tokens[0] in ("help", "aide", "--help", "-h"):
                help_text = self._generate_help()
                self.send_help(platform_payload, help_text)
                return

            # Step 4: Parse command
            cmd_name = tokens[0]
            if self.registry is None:
                self.send_error(
                    platform_payload,
                    "Command registry not initialized.",
                )
                return
            cmd = self.registry.get_command(cmd_name)

            if cmd is None:
                self.send_error(
                    platform_payload,
                    f"Unknown command: `{cmd_name}`. Type `help` for usage.",
                )
                return

            # Step 5: Create context (platform-specific)
            ctx = self.create_context(platform_payload)

            # Step 6: Parse arguments
            arg_tokens = tokens[1:]
            parsed = self.parser.parse(cmd, arg_tokens)

            # Step 7: Execute handler
            if parsed.subcommand:
                parsed.subcommand.command.handler(ctx, **parsed.subcommand.args)
            else:
                cmd.handler(ctx, **parsed.args)

        except CommandParseError as e:
            self.send_error(platform_payload, str(e))
            logger.warning(
                "command_parse_error",
                error=str(e),
                namespace=self.registry.namespace if self.registry else "unknown",
            )
        except Exception as e:  # pylint: disable=broad-except
            self.send_error(
                platform_payload, "An error occurred processing your command."
            )
            logger.exception(
                "unhandled_command_error",
                error=str(e),
                namespace=self.registry.namespace if self.registry else "unknown",
            )

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize command text (respects quotes).

        Args:
            text: Command text from user

        Returns:
            List of tokens, respecting quoted strings
        """
        tokens: List[str] = []
        current: List[str] = []
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

    def _generate_help(self) -> str:
        """Generate help text from registry.

        Returns:
            Formatted help text
        """
        if self.registry is None:
            return "No command registry available."
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
