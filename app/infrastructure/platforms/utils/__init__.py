"""Utility functions for platform commands infrastructure.

Includes help text generation, schema inference, and i18n support.
"""

from infrastructure.platforms.utils.help import (
    generate_help_text,
    generate_usage_line,
    get_argument_by_name,
)
from infrastructure.platforms.utils.schema_inference import (
    infer_arguments_from_schema,
)

__all__ = [
    "generate_help_text",
    "generate_usage_line",
    "get_argument_by_name",
    "infer_arguments_from_schema",
]
