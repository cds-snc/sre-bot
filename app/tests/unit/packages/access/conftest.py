"""Shared access-package test isolation fixtures.

Guarantees all access unit tests run in isolation from host/CI env vars and
from any local `.env` values.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from packages.access.catalog import providers as catalog_providers
from packages.access.common.config.loaders import EnvConfigLoader
from packages.access.common.providers import get_access_runtime_config
from packages.access.common.settings import AccessSettings, get_access_settings
from packages.access.request import providers as request_providers
from packages.access.sync import providers as sync_providers


def _clear_access_caches() -> None:
    """Reset all cached singleton providers used by the access feature tests."""
    get_access_settings.cache_clear()
    get_access_runtime_config.cache_clear()

    sync_providers.get_access_sync_adapters.cache_clear()
    sync_providers.get_sync_run_repository.cache_clear()
    sync_providers.get_access_sync_coordinator.cache_clear()

    request_providers.get_access_request_repository.cache_clear()
    request_providers.get_access_request_service.cache_clear()

    catalog_providers._build_parser_map.cache_clear()
    catalog_providers.get_catalog_service.cache_clear()


def _clear_access_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every ACCESS_* variable so tests cannot read external values."""
    for key in tuple(os.environ):
        if key.startswith("ACCESS_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _access_root_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env and singleton isolation for every access test."""
    # Force settings models to ignore local .env while tests execute.
    monkeypatch.setitem(AccessSettings.model_config, "env_file", None)
    monkeypatch.setitem(EnvConfigLoader._EnvModel.model_config, "env_file", None)

    _clear_access_env(monkeypatch)
    _clear_access_caches()
    yield
    _clear_access_caches()
