"""Unit tests for packages.access.catalog package initialization behavior."""

import importlib

import pytest


def _reload_catalog_package():
    module = importlib.import_module("packages.access.catalog")
    return importlib.reload(module)


@pytest.mark.unit
def test_catalog_startup_warmup_validates_runtime_config(monkeypatch):
    catalog_pkg = _reload_catalog_package()

    runtime_config_called = False
    provider_warm_called = False

    def _runtime_config() -> object:
        nonlocal runtime_config_called
        runtime_config_called = True
        return object()

    class _Settings:
        enabled = True

    def _warm_provider() -> object:
        nonlocal provider_warm_called
        provider_warm_called = True
        return object()

    monkeypatch.setattr(catalog_pkg, "get_access_runtime_config", _runtime_config, raising=False)
    monkeypatch.setattr(catalog_pkg, "get_catalog_settings", lambda: _Settings())
    monkeypatch.setattr(catalog_pkg, "get_catalog_service", _warm_provider)

    catalog_pkg.startup_warmup(
        logger=type(
            "L",
            (),
            {
                "info": lambda *a, **k: None,
                "warning": lambda *a, **k: None,
                "error": lambda *a, **k: None,
            },
        )()
    )

    assert runtime_config_called is True
    assert provider_warm_called is True


@pytest.mark.unit
def test_catalog_startup_warmup_raises_when_enabled_runtime_config_is_invalid(
    monkeypatch,
):
    catalog_pkg = _reload_catalog_package()

    class _Settings:
        enabled = True

    monkeypatch.setattr(catalog_pkg, "get_catalog_settings", lambda: _Settings())
    monkeypatch.setattr(
        catalog_pkg,
        "get_access_runtime_config",
        lambda: (_ for _ in ()).throw(RuntimeError("invalid runtime config")),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="invalid runtime config"):
        catalog_pkg.startup_warmup(
            logger=type(
                "L",
                (),
                {
                    "info": lambda *a, **k: None,
                    "warning": lambda *a, **k: None,
                    "error": lambda *a, **k: None,
                },
            )()
        )
