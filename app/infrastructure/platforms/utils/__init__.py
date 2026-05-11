"""Utility functions for platform commands infrastructure.

Includes help text generation, schema inference, and i18n support.
"""

from infrastructure.platforms.utils.slack_help import (
    SlackHelpGenerator,
    build_slack_command_signature,
    build_slack_display_path,
    generate_slack_help_text,
    generate_usage_line,
    get_argument_by_name,
)

__all__ = [
    "SlackHelpGenerator",
    "build_slack_command_signature",
    "build_slack_display_path",
    "generate_slack_help_text",
    "generate_usage_line",
    "get_argument_by_name",
]
