"""Command framework data models."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class ArgumentType(Enum):
    """Supported argument types."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    FLOAT = "float"
    EMAIL = "email"


@dataclass
class Argument:
    """Command argument definition.

    Attributes:
        name: Argument name (e.g., "email" or "--verbose")
        type: ArgumentType for validation and coercion
        required: Whether argument is required
        flag: True for flag arguments (e.g., --verbose)
        default: Default value if not provided
        description: Human-readable description
        description_key: Translation key for description
        choices: List of valid values
        description_key: Translation key for description

    Examples:
        Positional: Argument("email", type=ArgumentType.EMAIL, required=True)
        Flag: Argument("--verbose", type=ArgumentType.BOOLEAN, flag=True)
        Optional: Argument("provider", type=ArgumentType.STRING, required=False, default="google")
    """

    name: str
    type: ArgumentType = ArgumentType.STRING
    required: bool = True
    flag: bool = False  # True for --flags
    default: Any = None
    description: str = ""
    description_key: Optional[str] = None  # Translation key
    choices: Optional[List[Any]] = None  # Valid values

    def __post_init__(self):
        """Validate argument configuration."""
        if self.flag and not self.name.startswith("--"):
            raise ValueError(f"Flag arguments must start with '--': {self.name}")
        if self.flag and self.required:
            raise ValueError(f"Flag arguments cannot be required: {self.name}")


@dataclass
class Command:
    """Command definition with metadata for auto-help generation.

    Attributes:
        name: Command name
        handler: Callable to execute command
        description: Human-readable description
        description_key: Translation key for description
        args: List of Argument definitions
        subcommands: Dict of nested commands
        examples: List of usage examples
        example_keys: Translation keys for examples

    Example:
        @registry.command(
            name="add",
            description_key="groups.commands.add.description",
            args=[
                Argument("member_email", type=ArgumentType.EMAIL),
                Argument("group_id", type=ArgumentType.STRING),
                Argument("justification", type=ArgumentType.STRING, required=False)
            ]
        )
        def add_member(ctx: CommandContext, member_email: str, group_id: str, justification: str = None):
            ...
    """

    name: str
    handler: Callable
    description: str = ""
    description_key: Optional[str] = None  # Translation key
    args: List[Argument] = field(default_factory=list)
    subcommands: Dict[str, "Command"] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    example_keys: List[str] = field(default_factory=list)  # Translation keys

    def add_subcommand(self, subcommand: "Command") -> None:
        """Add a nested subcommand."""
        self.subcommands[subcommand.name] = subcommand

    def get_required_args(self) -> List[Argument]:
        """Get required positional arguments."""
        return [arg for arg in self.args if arg.required and not arg.flag]

    def get_optional_args(self) -> List[Argument]:
        """Get optional positional arguments."""
        return [arg for arg in self.args if not arg.required and not arg.flag]

    def get_flags(self) -> List[Argument]:
        """Get flag arguments."""
        return [arg for arg in self.args if arg.flag]


@dataclass
class ParsedCommand:
    """Result of command parsing.

    Attributes:
        command: The Command definition that was matched
        args: Dict of parsed and validated arguments
        raw_text: Original command text
        subcommand: Parsed subcommand if nested
    """

    command: Command
    args: Dict[str, Any]  # Parsed and validated arguments
    raw_text: str
    subcommand: Optional["ParsedCommand"] = None
