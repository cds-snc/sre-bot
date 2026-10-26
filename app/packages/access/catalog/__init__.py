"""Access Catalog package entry point.

Registers HTTP routes and warms singleton providers at startup.
No Slack commands are registered in this initial iteration — Slack
interaction support is deferred to the next iteration.
"""

from contracts.plugins.namespace import hookimpl
from packages.access.catalog.interactions.http import router as access_catalog_router
from packages.access.catalog.providers import get_catalog_service
from packages.access.common.providers import get_access_runtime_config


@hookimpl
def register_routes(app) -> None:
    """Register Access Catalog HTTP routes under /api/v1."""
    app.include_router(access_catalog_router, prefix="/api/v1")


@hookimpl
def startup_warmup(logger) -> None:
    """Warm the runtime config and catalog service at startup."""
    # Validate runtime config and provider assembly before serving traffic.
    get_access_runtime_config()
    get_catalog_service()
    logger.info("access_catalog_providers_warmed")


__all__ = ["access_catalog_router"]
