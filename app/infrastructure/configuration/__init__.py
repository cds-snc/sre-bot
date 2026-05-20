"""Infrastructure configuration module - public API.

This module provides centralized configuration management for the SRE Bot
application using Pydantic BaseSettings with domain-based organization.

Exports:
    settings: Singleton Settings instance (main configuration object)
    Settings: Main settings class (for testing/overrides)
    RetrySettings: Retry system settings class (for testing)

Example:
    ```python
    from infrastructure.configuration import get_settings

    settings = get_settings()

    # Access settings
    slack_token = settings.slack.SLACK_TOKEN
    aws_region = settings.aws.AWS_REGION
    retry_enabled = settings.retry.enabled

    # Check environment
    if settings.is_production:
        # Production-specific logic...
    ```
"""

from infrastructure.configuration.app import AppSettings, get_app_settings
from infrastructure.configuration.settings import Settings, get_settings
from infrastructure.configuration.infrastructure.retry import RetrySettings

__all__ = [
    "AppSettings",
    "Settings",
    "RetrySettings",
    "get_app_settings",
    "get_settings",
]
