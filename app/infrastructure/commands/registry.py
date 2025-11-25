"""Command registry for registration and discovery."""

from typing import Callable, Dict, List, Optional

from core.logging import get_module_logger
from infrastructure.commands.models import Command, Argument

logger = get_module_logger()


class CommandRegistry:
    """Registry for command registration and discovery.

    Supports nested commands (subcommands) and auto-help generation.

    Attributes:
        namespace: Module namespace for the registry (e.g., "groups", "incidents")
        _commands: Dict of registered commands

    Example:
        registry = CommandRegistry("groups")

        @registry.command(
            name="list",
            description_key="groups.commands.list.description",
            args=[Argument("provider", type=ArgumentType.STRING, required=False)]
        )
        def list_groups(ctx: CommandContext, provider: str = None):
            ...

        @registry.subcommand("list", name="managed")
        def list_managed_groups(ctx: CommandContext):
            ...
    """

    def __init__(self, namespace: str):
        """Initialize registry.

        Args:
            namespace: Module namespace for commands
        """
        self.namespace = namespace
        self._commands: Dict[str, Command] = {}

    def command(
        self,
        name: str,
        description: str = "",
        description_key: Optional[str] = None,
        args: List[Argument] = None,
        examples: List[str] = None,
        example_keys: List[str] = None,
    ) -> Callable:
        """Decorator to register a command with handler.

        Args:
            name: Command name
            description: Human-readable description
            description_key: Translation key for description
            args: List of Argument definitions
            examples: List of usage examples
            example_keys: List of translation keys for examples

        Returns:
            Decorator function that registers the handler
        """

        def decorator(handler: Callable) -> Callable:
            cmd = Command(
                name=name,
                handler=handler,
                description=description,
                description_key=description_key,
                args=args or [],
                examples=examples or [],
                example_keys=example_keys or [],
            )
            self._commands[name] = cmd
            logger.debug("registered command", namespace=self.namespace, name=name)
            return handler

        return decorator

    def subcommand(
        self,
        parent_name: str,
        name: str,
        description: str = "",
        description_key: Optional[str] = None,
        args: List[Argument] = None,
        examples: List[str] = None,
        example_keys: List[str] = None,
    ) -> Callable:
        """Decorator to register a subcommand.

        Args:
            parent_name: Name of parent command
            name: Subcommand name
            description: Human-readable description
            description_key: Translation key for description
            args: List of Argument definitions
            examples: List of usage examples
            example_keys: List of translation keys for examples

        Returns:
            Decorator function

        Raises:
            ValueError: If parent command not found
        """

        def decorator(handler: Callable) -> Callable:
            parent = self._commands.get(parent_name)
            if parent is None:
                raise ValueError(
                    f"Parent command '{parent_name}' not found in {self.namespace}"
                )

            subcmd = Command(
                name=name,
                handler=handler,
                description=description,
                description_key=description_key,
                args=args or [],
                examples=examples or [],
                example_keys=example_keys or [],
            )
            parent.add_subcommand(subcmd)
            logger.debug(
                "registered subcommand",
                namespace=self.namespace,
                parent=parent_name,
                name=name,
            )
            return handler

        return decorator

    def get_command(self, name: str) -> Optional[Command]:
        """Get command by name.

        Args:
            name: Command name

        Returns:
            Command object or None if not found
        """
        return self._commands.get(name)

    def list_commands(self) -> List[Command]:
        """Get all registered commands.

        Returns:
            List of all commands in this registry
        """
        return list(self._commands.values())

    def find_command(self, parts: List[str]) -> Optional[Command]:
        """Find command by parts (supports subcommands).

        Args:
            parts: List of command parts (e.g., ["list"] or ["list", "managed"])

        Returns:
            Command object or None if not found

        Example:
            registry = CommandRegistry("groups")
            cmd = registry.find_command(["list", "managed"])
        """
        if not parts:
            return None

        cmd = self._commands.get(parts[0])
        if cmd is None:
            return None

        # Navigate subcommands
        for part in parts[1:]:
            if part not in cmd.subcommands:
                return None
            cmd = cmd.subcommands[part]

        return cmd
