"""Infrastructure configuration module - public API.

This module provides centralized configuration management for the SRE Bot
application using Pydantic BaseSettings with domain-based organization.

Exports:
    RetrySettings: Retry system settings class (for testing)

Example:
    ```python
    from infrastructure.configuration.infrastructure.retry import get_retry_settings

    retry_settings = get_retry_settings()

    # Access narrow settings slices
    retry_enabled = retry_settings.enabled
    ```
"""

from infrastructure.configuration.infrastructure.retry import RetrySettings

__all__ = [
    "RetrySettings",
]
