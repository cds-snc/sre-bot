"""
Factory functions for dependency injection.

Provides application-scoped singleton providers for core infrastructure services.
"""

from functools import lru_cache
from infrastructure.configuration import Settings
from infrastructure.observability import get_module_logger


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


def get_logger():
    """
    Get logger instance for dependency injection.

    Returns:
        Bound logger for the current request/execution context.

    Usage:
        @app.get("/debug")
        def debug_endpoint(logger: LoggerDep) -> dict:
            logger.info("debug_endpoint_called")
            return {"status": "ok"}
    """
    return get_module_logger()
