"""Access Catalog singleton provider functions.

Each function is decorated with ``@lru_cache(maxsize=1)`` to ensure a single
instance per process lifetime.

To substitute a dependency in tests, patch the provider function itself at
module scope — never bypass providers.
"""

from functools import lru_cache

from infrastructure.directory import get_directory_provider
from packages.access.catalog.parsers import (
    AwsCatalogSlugParser,
    CatalogSlugParser,
    FallbackCatalogSlugParser,
)
from packages.access.catalog.service import CatalogService
from packages.access.common.providers import get_access_runtime_config
from packages.access.common.settings import AccessCatalogSettings, get_access_settings


def get_catalog_settings() -> AccessCatalogSettings:
    """Return the catalog settings slice from the unified access settings."""
    return get_access_settings().catalog


@lru_cache(maxsize=1)
def _build_parser_map() -> dict[str, CatalogSlugParser]:
    """Build the platform key → parser mapping from runtime config.

    Parser config (``known_envs``) is read from the typed ``catalog_extensions``
    in the Access runtime config when present.  Platforms without parser config
    fall back to ``FallbackCatalogSlugParser``.
    """
    runtime_config = get_access_runtime_config()
    parsers: dict[str, CatalogSlugParser] = {}

    for platform_key in runtime_config.platforms:
        known_envs = set()
        if runtime_config.catalog_extensions:
            parser_config = runtime_config.catalog_extensions.parsers.get(platform_key)
            if parser_config:
                known_envs = set(parser_config.known_envs)

        if platform_key == "aws":
            parsers[platform_key] = AwsCatalogSlugParser(known_envs=known_envs)
        else:
            parsers[platform_key] = FallbackCatalogSlugParser()

    return parsers


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    """Return the singleton CatalogService.

    Wires together:
    - AccessRuntimeConfig (platform policy and group naming).
    - DirectoryProvider (IDP group discovery and membership checks).
    - Parser map (token decomposition per platform).
    - Display names from typed catalog extensions (optional).
    """
    runtime_config = get_access_runtime_config()
    directory = get_directory_provider()
    parser_map = _build_parser_map()

    display_names: dict[str, str] = {}
    if runtime_config.catalog_extensions:
        display_names = dict(runtime_config.catalog_extensions.platform_display_names)

    return CatalogService(
        runtime_config=runtime_config,
        directory=directory,
        parsers=parser_map,
        display_names=display_names,
    )
