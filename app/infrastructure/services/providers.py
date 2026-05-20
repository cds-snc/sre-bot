"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache

from infrastructure.configuration import Settings
from infrastructure.configuration.app import (
    AppSettings,
)
from infrastructure.configuration.app import (
    get_app_settings as _get_app_settings,
)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Deprecated: get application-scoped settings singleton.

    This is the single source of truth for settings across the entire application.
    The @lru_cache decorator ensures only ONE instance is created per process,
    even if called from multiple packages.

    Infrastructure packages should use this directly to ensure singleton consistency:
        from infrastructure.services.providers import get_settings
        settings = get_settings()

    Application code should use the DI type alias for testability:
        from infrastructure.services import SettingsDep
        @router.get("/config")
        def get_config(settings: SettingsDep):
            return settings.dict()

    Returns:
        Settings: Cached settings instance loaded from environment.

    Note:
        Deprecated. Prefer domain-specific settings providers
        (for example get_slack_settings(), get_server_settings()).
    """
    return Settings()


def get_app_settings() -> AppSettings:
    """Get application-scoped app settings singleton."""
    return _get_app_settings()
