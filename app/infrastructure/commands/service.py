"""Command service for dependency injection.

Provides a class-based interface to the command framework for easier DI and testing.
"""

from typing import TYPE_CHECKING, Dict, List

from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.models import Command
from infrastructure.commands.parser import CommandParser

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

import structlog

logger = structlog.get_logger(__name__)


class CommandService:
    """Centralized command service for the application.

    Provides a single registry for all commands across all modules,
    with support for dependency injection and testing.

    This service wraps the CommandRegistry pattern with a service interface
    to support dependency injection and easier testing with mocks.

    Usage:
        # Via dependency injection
        import shlex
        from infrastructure.services import CommandServiceDep

        @router.post("/commands/execute")
        def execute_command(
            command_service: CommandServiceDep,
            command_text: str
        ):
            # Get registry for namespace
            registry = command_service.get_registry("groups")

            # Tokenize command text
            tokens = shlex.split(command_text)
            cmd_name = tokens[0]
            arg_tokens = tokens[1:]

            # Look up command in registry
            cmd = registry.get(cmd_name)
            if not cmd:
                return {"error": f"Unknown command: {cmd_name}"}

            # Parse and validate arguments
            parsed = command_service.parser.parse(cmd, arg_tokens)

            # Execute command handler
            cmd.handler(ctx, **parsed.args)
            return {"status": "ok"}

        # Direct instantiation
        from infrastructure.services import get_settings
        from infrastructure.commands import CommandService

        settings = get_settings()
        service = CommandService(settings)
        registry = service.get_registry("mymodule")
    """

    def __init__(self, settings: "Settings"):
        """Initialize command service.

        Args:
            settings: Settings instance (required, passed from provider).
        """
        self._settings = settings
        self._registries: Dict[str, CommandRegistry] = {}
        self._parser = CommandParser()

        logger.info("initialized_command_service")

    def get_registry(self, namespace: str) -> CommandRegistry:
        """Get or create a command registry for a namespace.

        Args:
            namespace: Module namespace (e.g., "groups", "incidents")

        Returns:
            CommandRegistry for the given namespace
        """
        if namespace not in self._registries:
            self._registries[namespace] = CommandRegistry(namespace)
            logger.info("created_command_registry", namespace=namespace)

        return self._registries[namespace]

    def list_namespaces(self) -> List[str]:
        """List all registered command namespaces.

        Returns:
            List of namespace strings
        """
        return list(self._registries.keys())

    def get_all_commands(self) -> Dict[str, List[Command]]:
        """Get all commands from all registries.

        Returns:
            Dict mapping namespace to list of commands
        """
        return {
            namespace: list(registry._commands.values())
            for namespace, registry in self._registries.items()
        }

    @property
    def parser(self) -> CommandParser:
        """Access the command parser for direct use.

        The parser validates command arguments against Command schemas.
        It requires pre-tokenized input and a Command object.

        Returns:
            CommandParser instance

        Example:
            import shlex
            from infrastructure.services import CommandServiceDep

            @router.post("/api/commands")
            def handle_command(
                service: CommandServiceDep,
                text: str
            ):
                # Get registry
                registry = service.get_registry("groups")

                # Tokenize user input
                tokens = shlex.split(text)
                cmd_name = tokens[0]
                arg_tokens = tokens[1:]

                # Look up command
                cmd = registry.get(cmd_name)
                if not cmd:
                    return {"error": "Unknown command"}

                # Parse and validate arguments
                parsed = service.parser.parse(cmd, arg_tokens)

                # Execute handler
                cmd.handler(ctx, **parsed.args)
                return {"status": "ok"}
        """
        return self._parser
