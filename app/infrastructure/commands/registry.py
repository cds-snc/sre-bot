"""Command registry for registration and discovery."""

from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Any,
    Type,
    Union,
    get_origin,
    get_args,
    TYPE_CHECKING,
)
from uuid import uuid4
from enum import Enum

import structlog

from pydantic import BaseModel, ValidationError, EmailStr
from infrastructure.commands.models import Command, Argument, ArgumentType


if TYPE_CHECKING:
    from infrastructure.commands import CommandContext

logger = structlog.get_logger()


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
        args: Optional[List[Argument]] = None,
        examples: Optional[List[str]] = None,
        example_keys: Optional[List[str]] = None,
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
        args: Optional[List[Argument]] = None,
        examples: Optional[List[str]] = None,
        example_keys: Optional[List[str]] = None,
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

    def schema_command(
        self,
        name: str,
        schema: Type[BaseModel],
        description: str = "",
        description_key: Optional[str] = None,
        examples: Optional[List[str]] = None,
        example_keys: Optional[List[str]] = None,
        mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        args: Optional[List[Argument]] = None,
    ) -> Callable:
        """Register a command using a Pydantic schema for validation.

        The schema should have all required fields except 'requestor' and
        'idempotency_key', which are injected automatically from context.

        Args:
            name: Command name
            schema: Pydantic BaseModel schema (e.g., AddMemberRequest)
            description: Human-readable description
            description_key: Translation key for description
            examples: List of usage examples
            example_keys: List of translation keys for examples
            mapper: Optional function to transform parsed kwargs before validation
            args: Optional explicit Argument definitions (if not provided, auto-generated)

        Returns:
            Decorator that wraps handler to accept (ctx, request) signature

        Example:
            @registry.schema_command(
                name="add",
                schema=schemas.AddMemberRequest,
                description_key="groups.commands.add.description",
                args=[
                    Argument("member_email", type=ArgumentType.EMAIL, required=True),
                    Argument("group_id", type=ArgumentType.STRING, required=True),
                    Argument("provider", type=ArgumentType.STRING, required=True),
                    Argument("justification", type=ArgumentType.STRING, required=False),
                ]
            )
            def add_member_command(ctx: CommandContext, request: schemas.AddMemberRequest):
                return service.add_member(request)
        """

        def decorator(handler: Callable) -> Callable:
            # Use provided arguments or auto-generate from schema
            schema_args = args or self._schema_to_arguments(schema)

            def wrapper(ctx: "CommandContext", **parsed_kwargs) -> Any:
                # Apply optional mapper for complex transformations
                if mapper:
                    parsed_kwargs = mapper(parsed_kwargs)

                # Note: Platform-specific preprocessing (e.g., Slack @mention resolution)
                # is now handled by CommandProvider._preprocess_arguments() before this
                # wrapper is called. This keeps the registry platform-agnostic.

                # Inject context fields
                parsed_kwargs["requestor"] = ctx.user_email
                if "idempotency_key" not in parsed_kwargs:
                    parsed_kwargs["idempotency_key"] = str(uuid4())

                # Validate using Pydantic
                try:
                    validated_request = schema(**parsed_kwargs)
                except ValidationError as e:
                    # Convert Pydantic errors to user-friendly messages
                    error_details = []
                    for error in e.errors():
                        field = error.get("loc", ("unknown",))[0]
                        msg = error.get("msg", "Validation failed")
                        error_details.append(f"{field}: {msg}")

                    error_msg = ctx.translate(
                        "commands.errors.validation_failed",
                        errors="; ".join(error_details),
                    )
                    ctx.respond(error_msg)
                    return

                # Call actual handler with validated request
                return handler(ctx, validated_request)

            # Register with existing command infrastructure
            cmd = Command(
                name=name,
                handler=wrapper,
                description=description,
                description_key=description_key,
                args=schema_args,
                examples=examples or [],
                example_keys=example_keys or [],
            )
            self._commands[name] = cmd
            logger.debug(
                "registered schema command", namespace=self.namespace, name=name
            )
            return handler

        return decorator

    def _schema_to_arguments(self, schema: Type[BaseModel]) -> List[Argument]:
        """Convert Pydantic schema fields to Argument definitions.

        Introspects schema fields to generate matching Argument objects.
        Skips 'requestor', 'idempotency_key', and 'metadata' (auto-injected).

        Args:
            schema: Pydantic BaseModel class

        Returns:
            List of Argument definitions
        """
        args = []
        for field_name, field_info in schema.model_fields.items():
            # Skip auto-injected fields
            if field_name in ("requestor", "idempotency_key", "metadata"):
                continue

            # Map Pydantic types to ArgumentType
            arg_type = self._pydantic_type_to_argument_type(field_info.annotation)

            # Extract constraints and metadata
            required = field_info.is_required()
            description = field_info.description or ""

            # Handle Enum choices
            choices = None
            origin_type = field_info.annotation
            if isinstance(origin_type, type) and issubclass(origin_type, Enum):
                choices = [e.value for e in origin_type]

            args.append(
                Argument(
                    name=field_name,
                    type=arg_type,
                    required=required,
                    choices=choices,
                    description=description,
                )
            )

        return args

    @staticmethod
    def _pydantic_type_to_argument_type(pydantic_type) -> ArgumentType:
        """Map Pydantic field types to ArgumentType enum.

        Args:
            pydantic_type: Pydantic field type annotation

        Returns:
            Corresponding ArgumentType
        """
        # Handle Optional[T] and other generic types
        origin = get_origin(pydantic_type)
        if origin is Union:
            # Get first non-None type from Union (e.g., Optional[str] -> str)
            args = get_args(pydantic_type)
            for arg in args:
                if arg is not type(None):
                    return CommandRegistry._pydantic_type_to_argument_type(arg)

        # Direct type mapping
        type_mapping = {
            str: ArgumentType.STRING,
            int: ArgumentType.INTEGER,
            float: ArgumentType.FLOAT,
            bool: ArgumentType.BOOLEAN,
            EmailStr: ArgumentType.EMAIL,
        }

        return type_mapping.get(pydantic_type, ArgumentType.STRING)
