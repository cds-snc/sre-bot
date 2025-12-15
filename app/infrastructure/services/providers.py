"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from infrastructure.configuration import Settings


@lru_cache
def get_settings() -> Settings:
    """
    Get application-scoped settings singleton.

    Returns:
        Settings: Cached settings instance loaded from environment.

    Usage:
        @app.get("/config")
        def get_config(settings: SettingsDep) -> dict:
            return settings.dict()
    """
    return Settings()
