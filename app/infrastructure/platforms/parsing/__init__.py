"""Command argument parsing infrastructure.
To be deprecated
Provides quote-aware tokenization and argument parsing for platform commands
(Slack) with full type validation and schema integration.
"""

from infrastructure.platforms.parsing.models import (
    Argument,
    ArgumentType,
    ArgumentParsingError,
)
from infrastructure.platforms.parsing.parser import CommandArgumentParser

__all__ = [
    "Argument",
    "ArgumentType",
    "ArgumentParsingError",
    "CommandArgumentParser",
]
