"""Test data factories for command framework testing.

Provides deterministic, immutable test data builders for:
- Arguments
- Commands
- CommandContext
- CommandRegistry
"""

from infrastructure.commands.models import (
    Argument,
    ArgumentType,
    Command,
)
from infrastructure.commands.context import CommandContext


def make_argument(
    name: str = "arg",
    arg_type: ArgumentType = None,
    required: bool = True,
    flag: bool = False,
    default=None,
    choices=None,
    description: str = "",
    description_key=None,
) -> Argument:
    """Create an Argument instance.

    Args:
        name: Argument name
        arg_type: ArgumentType (default: STRING)
        required: Whether required
        flag: Whether a flag argument
        default: Default value
        choices: Valid values
        description: Human-readable description
        description_key: Translation key

    Returns:
        Argument instance
    """
    arg_type = arg_type or ArgumentType.STRING
    return Argument(
        name=name,
        type=arg_type,
        required=required,
        flag=flag,
        default=default,
        choices=choices,
        description=description,
        description_key=description_key,
    )


def make_command(
    name: str = "test",
    handler=None,
    args=None,
    description: str = "",
    description_key=None,
    examples=None,
    example_keys=None,
) -> Command:
    """Create a Command instance.

    Args:
        name: Command name
        handler: Handler callable (default: no-op lambda)
        args: List of Arguments
        description: Human-readable description
        description_key: Translation key
        examples: List of example strings
        example_keys: List of example translation keys

    Returns:
        Command instance
    """
    handler = handler or (lambda ctx, **kwargs: None)
    return Command(
        name=name,
        handler=handler,
        args=args or [],
        description=description,
        description_key=description_key,
        examples=examples or [],
        example_keys=example_keys or [],
    )


def make_command_context(
    platform: str = "slack",
    user_id: str = "U12345",
    user_email: str = "test@example.com",
    channel_id: str = "C12345",
    locale: str = "en-US",
    metadata=None,
    correlation_id: str = None,
    translator=None,
    responder=None,
) -> CommandContext:
    """Create a CommandContext instance.

    Args:
        platform: Platform name
        user_id: User ID
        user_email: User email
        channel_id: Channel ID
        locale: Locale string
        metadata: Metadata dict
        correlation_id: Correlation ID
        translator: Translation callable
        responder: Response channel

    Returns:
        CommandContext instance
    """
    ctx = CommandContext(
        platform=platform,
        user_id=user_id,
        user_email=user_email,
        channel_id=channel_id,
        locale=locale,
        metadata=metadata or {},
        correlation_id=correlation_id,
    )
    ctx._translator = translator
    ctx._responder = responder
    return ctx
