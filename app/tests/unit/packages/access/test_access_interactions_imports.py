"""Fail-first tests for Sprint 1 access interactions module migration (GAP-10)."""

import importlib

import pytest

EXPECTED_INTERACTIONS_MODULES = (
    "packages.access.catalog.interactions.http",
    "packages.access.request.interactions.http",
    "packages.access.sync.interactions.http",
    "packages.access.sync.interactions.ingress",
    "packages.access.sync.interactions.slack",
)


@pytest.mark.unit
@pytest.mark.parametrize("module_name", EXPECTED_INTERACTIONS_MODULES)
def test_access_interactions_modules_are_importable(module_name: str) -> None:
    """All Sprint 1 interactions modules should be importable."""
    module = importlib.import_module(module_name)

    assert module is not None


@pytest.mark.unit
def test_access_package_router_exports_point_to_interactions_http_modules() -> None:
    """Package entrypoints should export routers from interactions.http modules."""
    catalog_pkg = importlib.import_module("packages.access.catalog")
    request_pkg = importlib.import_module("packages.access.request")
    sync_pkg = importlib.import_module("packages.access.sync")
    catalog_http = importlib.import_module("packages.access.catalog.interactions.http")
    request_http = importlib.import_module("packages.access.request.interactions.http")
    sync_http = importlib.import_module("packages.access.sync.interactions.http")

    assert catalog_pkg.access_catalog_router is catalog_http.router
    assert request_pkg.access_requests_router is request_http.router
    assert sync_pkg.access_sync_router is sync_http.router
