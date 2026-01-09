"""Command framework for platform-agnostic command handling.

This framework provides:
- CommandRegistry: Register and discover commands
- CommandContext: Platform-agnostic execution context
- CommandParser: Parse and validate command arguments
- SlackCommandProvider: Slack Bolt SDK integration (in providers)
- CommandService: Service wrapper for dependency injection

Example:
    from infrastructure.commands import (
        CommandRegistry, CommandContext, Argument, ArgumentType
    )

    registry = CommandRegistry("mymodule")

    @registry.command(
        name="hello",
        description="Say hello to someone",
        args=[Argument("name", type=ArgumentType.STRING)]
    )
    def hello_command(ctx: CommandContext, name: str):
        ctx.respond(f"Hello, {name}!")

    # In Slack bot registration:
    from infrastructure.commands.providers.slack import SlackCommandProvider
    from infrastructure.services import get_settings

    settings = get_settings()
    adapter = SlackCommandProvider(settings=settings, config={})
    bot.command("/sre mymodule")(adapter.handle)

Recommended Usage (Service Pattern with DI):
    from infrastructure.services import CommandServiceDep

    @router.post("/commands/register")
    def register_command(command_service: CommandServiceDep, module: str):
        registry = command_service.get_registry(module)
        commands = registry.get_all_commands()
        return {"module": module, "commands": len(commands)}
"""

from infrastructure.commands.models import (
    Command,
    Argument,
    ArgumentType,
    ParsedCommand,
)
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.parser import CommandParser, CommandParseError
from infrastructure.commands.context import CommandContext, ResponseChannel
from infrastructure.commands.providers.base import CommandProvider
from infrastructure.commands.service import CommandService
from infrastructure.commands.responses import (
    Button,
    ButtonStyle,
    Card,
    ErrorMessage,
    Field,
    SuccessMessage,
    ResponseFormatter,
    SlackResponseFormatter,
)

# Provider imports are available but not exported by default
# to avoid circular dependencies. Import directly from providers:
# from infrastructure.commands.providers.slack import SlackCommandProvider

__all__ = [
    # Models
    "Command",
    "Argument",
    "ArgumentType",
    "ParsedCommand",
    # Core
    "CommandRegistry",
    "CommandParser",
    "CommandParseError",
    "CommandContext",
    "ResponseChannel",
    # Service
    "CommandService",
    # Adapters
    "CommandProvider",
    # Responses
    "Button",
    "ButtonStyle",
    "Card",
    "ErrorMessage",
    "Field",
    "SuccessMessage",
    "ResponseFormatter",
    "SlackResponseFormatter",
]
