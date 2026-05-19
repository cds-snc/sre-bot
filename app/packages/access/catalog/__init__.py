"""Access Catalog package entry point.

Registers HTTP routes and warms singleton providers at startup.
No Slack commands are registered in this initial iteration — Slack
interaction support is deferred to the next iteration.
"""

from infrastructure.plugins import hookimpl
from packages.access.common.providers import get_access_runtime_config
from packages.access.catalog.providers import (
    get_catalog_service,
    get_catalog_settings,
)
from packages.access.catalog.interactions.http import router as access_catalog_router


@hookimpl
def register_routes(app) -> None:
    """Register Access Catalog HTTP routes under /api/v1."""
    app.include_router(access_catalog_router, prefix="/api/v1")


@hookimpl
def startup_warmup(logger) -> None:
    """Log effective Access Catalog settings and warm singletons at startup."""
    settings = get_catalog_settings()
    logger.info(
        "access_catalog_settings_loaded",
        enabled=settings.enabled,
    )

    if not settings.enabled:
        logger.warning(
            "access_catalog_disabled",
            hint="Set ACCESS_CATALOG_ENABLED=true to enable the feature.",
        )
        return

    # Validate runtime config and provider assembly before serving traffic.
    get_access_runtime_config()
    get_catalog_service()
    logger.info("access_catalog_providers_warmed")


__all__ = ["access_catalog_router"]
