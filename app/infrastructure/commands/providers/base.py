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
import shlex

from core.logging import get_module_logger
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.parser import CommandParser, CommandParseError
from infrastructure.commands.context import CommandContext
from infrastructure.i18n.translator import Translator
from infrastructure.i18n.resolvers import LocaleResolver
from infrastructure.i18n.models import TranslationKey, Locale

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
        self.parent_command: Optional[str] = None

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
        - Requestor User identification (user_id, user_email)
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

    @abstractmethod
    def _validate_payload(self, platform_payload: Any) -> None:
        """Optional: Validate platform payload structure.

        Subclasses can override to perform platform-specific validation
        before processing the command.

        Args:
            platform_payload: Platform-specific command data structure

        Raises:
            ValueError: If validation fails
        """
        ...

    @abstractmethod
    def preprocess_command_text(self, platform_payload: Any, text: str) -> str:
        """Preprocess command text before tokenization.

        Platform-specific transformations on raw text:
        - Slack: Resolve @mentions and #channels to emails/IDs
        - Teams: Resolve mentions to UPNs, etc.

        Args:
            platform_payload: Platform-specific payload for context (client, etc.)
            text: Raw command text from extract_command_text()

        Returns:
            Preprocessed text with platform identifiers resolved
        """
        return text

    @abstractmethod
    def _resolve_framework_locale(self, platform_payload: Any) -> str:
        """Resolve locale for framework operations (help, errors).

        Framework-level locale resolution without creating full context.
        Subclasses should implement platform-specific quick resolution.

        Args:
            platform_payload: Platform-specific command data structure

        Returns:
            Locale string (e.g., "en-US", "fr-FR")

        Default implementation: returns "en-US"
        """
        return "en-US"

    def _translate_or_fallback(
        self, translation_key: Optional[str], fallback: str, locale: str
    ) -> str:
        """Translate a message key or fall back to default text.

        Args:
            translation_key: Translation key (e.g., "commands.errors.unknown_command")
            fallback: Fallback text if translation not available
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Translated message or fallback text
        """
        if not translation_key or not self.translator:
            return fallback

        try:
            key = TranslationKey.from_string(translation_key)
            locale_enum = Locale.from_string(locale)
            return self.translator.translate_message(key, locale_enum)
        except Exception as e:  # pylint: disable=broad-except
            logger.debug(
                "translation_fallback",
                key=translation_key,
                error=str(e),
            )
            return fallback

    def _translate_error(
        self, error_key: str, locale: str, fallback: str, **variables: Any
    ) -> str:
        """Translate an error message with variable interpolation.

        Args:
            error_key: Error translation key (e.g., "commands.errors.unknown_command")
            locale: Locale string
            fallback: Fallback text if translation not available
            **variables: Variables for interpolation

        Returns:
            Translated error message or fallback
        """
        if not self.translator:
            return fallback

        try:
            key = TranslationKey.from_string(error_key)
            locale_enum = Locale.from_string(locale)
            return self.translator.translate_message(
                key, locale_enum, variables=variables
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.debug(
                "error_translation_fallback",
                key=error_key,
                error=str(e),
            )
            return fallback

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize command text using POSIX shell parsing rules.

        Uses Python's shlex module for robust parsing of quoted strings,
        escaped characters, and complex argument patterns.

        Args:
            text: Command text from user

        Returns:
            List of tokens with quotes removed and escapes processed

        Examples:
            >>> self._tokenize('list --user=@alice')
            ['list', '--user=@alice']

            >>> self._tokenize('add user "test new command" google')
            ['add', 'user', 'test new command', 'google']

            >>> self._tokenize('add user "value with \\"quotes\\"" google')
            ['add', 'user', 'value with "quotes"', 'google']

        Raises:
            ValueError: If text has unclosed quotes or invalid syntax
        """
        if not text:
            return []

        try:
            # Use POSIX mode for predictable behavior across platforms
            return shlex.split(text, posix=True)
        except ValueError as e:
            # Unclosed quotes, invalid escapes, etc.
            logger.error(
                "tokenization_error",
                text=text,
                error=str(e),
                namespace=self.registry.namespace if self.registry else "unknown",
            )
            # Graceful fallback: basic split (better than crashing)
            # This allows malformed commands to still attempt execution
            return text.split()

    def _generate_help(self, locale: str = "en-US") -> str:
        """Generate help text from registry with i18n support.

        Args:
            locale: Locale string (e.g., "en-US", "fr-FR")

        Returns:
            Formatted help text with translated descriptions and examples
        """
        if self.registry is None:
            return "No command registry available."

        command_prefix = (
            f"{self.parent_command} {self.registry.namespace}"
            if self.parent_command
            else self.registry.namespace
        )
        lines = [f"*{command_prefix.upper()} Commands*"]

        for cmd in self.registry.list_commands():
            lines.append(f"\n`/{command_prefix} {cmd.name}`")

            # Translate command description
            desc = self._translate_or_fallback(
                cmd.description_key, cmd.description, locale
            )
            if desc:
                lines.append(f"  {desc}")

            if cmd.args:
                for arg in cmd.args:
                    # Translate argument description if key available
                    arg_desc = self._translate_or_fallback(
                        arg.description_key, arg.description, locale
                    )
                    if arg.flag:
                        lines.append(f"  `{arg.name}` - {arg_desc}")
                    else:
                        # Translate required/optional terms
                        req_key = (
                            "commands.terms.required"
                            if arg.required
                            else "commands.terms.optional"
                        )
                        req_term = self._translate_or_fallback(
                            req_key, "required" if arg.required else "optional", locale
                        )
                        lines.append(f"  `{arg.name}` ({req_term}) - {arg_desc}")

            if cmd.examples:
                lines.append("  Examples:")
                for example in cmd.examples:
                    lines.append(f"    `/{command_prefix} {example}`")

            if cmd.subcommands:
                lines.append("  Subcommands:")
                for subcmd in cmd.subcommands.values():
                    lines.append(f"    `{subcmd.name}` - {subcmd.description}")

        return "\n".join(lines)

    def handle(self, platform_payload: Any) -> None:
        """Handle command execution (generic flow).

        Command flow:
        1. Acknowledge command receipt
        2. Validate payload
        3. Extract command text
        4. Preprocess command text
        5. Tokenize command text
        6. Resolve framework locale
        7. Handle help requests
        8. Ensure registry is available
        9. Look up command by name
        10. Parse and preprocess arguments
        11. Create context with finalized data
        12. Execute handler with parsed arguments

        Args:
            platform_payload: Platform-specific command data structure
        """
        # Step 1: Acknowledge command receipt
        self.acknowledge(platform_payload)
        try:
            try:
                # Step 2: Validate payload structure
                self._validate_payload(platform_payload)
            except ValueError as ve:
                framework_locale = self._resolve_framework_locale(platform_payload)
                error_msg = self._translate_error(
                    "commands.errors.invalid_payload",
                    framework_locale,
                    str(ve),
                    error=str(ve),
                )
                self.send_error(platform_payload, error_msg)
                logger.warning(
                    "invalid_command_payload",
                    error=str(ve),
                    namespace=self.registry.namespace if self.registry else "unknown",
                )
                return
            # Step 3-5: Extract command text (platform-specific) and tokenize
            text = self.extract_command_text(platform_payload)
            preprocessed_text = self.preprocess_command_text(platform_payload, text)
            tokens = self._tokenize(preprocessed_text) if preprocessed_text else []

            # Step 6: Resolve locale for framework operations (help, errors)
            framework_locale = self._resolve_framework_locale(platform_payload)

            # Step 7: Handle help requests
            if not tokens or tokens[0] in ("help", "aide", "--help", "-h"):
                help_text = self._generate_help(framework_locale)
                self.send_help(platform_payload, help_text)
                return

            # Step 8: Ensure registry is available
            if self.registry is None:
                error_msg = self._translate_error(
                    "commands.errors.registry_not_initialized",
                    framework_locale,
                    "Command registry not initialized.",
                )
                self.send_error(platform_payload, error_msg)
                return

            # Step 9: Look up command by name
            cmd_name = tokens[0]
            cmd = self.registry.get_command(cmd_name)

            if cmd is None:
                error_msg = self._translate_error(
                    "commands.errors.unknown_command",
                    framework_locale,
                    f"Unknown command: `{cmd_name}`. Type `help` for usage.",
                    command=cmd_name,
                )
                self.send_error(platform_payload, error_msg)
                return

            # Step 10: Parse and preprocess arguments
            arg_tokens = tokens[1:]
            parsed = self.parser.parse(cmd, arg_tokens)

            # Step 11: Create context with finalized data
            ctx = self.create_context(platform_payload)

            # Step 12: Execute handler with parsed arguments
            if parsed.subcommand:
                parsed.subcommand.command.handler(ctx, **parsed.args)
            else:
                cmd.handler(ctx, **parsed.args)
        except CommandParseError as e:
            framework_locale = self._resolve_framework_locale(platform_payload)
            error_msg = self._translate_error(
                "commands.errors.parse_error",
                framework_locale,
                str(e),
                error=str(e),
            )
            self.send_error(platform_payload, error_msg)
            logger.warning(
                "command_parse_error",
                error=str(e),
                namespace=self.registry.namespace if self.registry else "unknown",
            )
        except Exception as e:  # pylint: disable=broad-except
            framework_locale = self._resolve_framework_locale(platform_payload)
            error_msg = self._translate_error(
                "commands.errors.internal_error",
                framework_locale,
                "An error occurred processing your command.",
            )
            self.send_error(platform_payload, error_msg)
            logger.exception(
                "unhandled_command_error",
                error=str(e),
                namespace=self.registry.namespace if self.registry else "unknown",
            )
