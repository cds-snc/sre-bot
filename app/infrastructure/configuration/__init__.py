"""Infrastructure configuration module - public API.

This module provides centralized configuration management for the SRE Bot
application using Pydantic BaseSettings with domain-based organization.

Exports:
    AppSettings: App-level settings slice
    Settings: Main settings class (for testing/overrides)
    RetrySettings: Retry system settings class (for testing)

Example:
    ```python
    from infrastructure.configuration.app import get_app_settings
    from infrastructure.configuration.infrastructure.retry import get_retry_settings

    app_settings = get_app_settings()
    retry_settings = get_retry_settings()

    # Access narrow settings slices
    retry_enabled = retry_settings.enabled

    # Check environment
    if app_settings.ENVIRONMENT == "production":
        # Production-specific logic...
    ```
"""

from infrastructure.configuration.app import AppSettings, get_app_settings
from infrastructure.configuration.settings import Settings
from infrastructure.configuration.infrastructure.retry import RetrySettings

__all__ = [
    "AppSettings",
    "Settings",
    "RetrySettings",
    "get_app_settings",
]
