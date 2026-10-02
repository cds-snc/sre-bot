"""Naming tests for the Access Sync application service and its interface."""

import importlib
from typing import get_type_hints

import pytest


@pytest.mark.unit
def test_sync_application_module_exports_application_service_symbols() -> None:
    """The application module exposes the concrete service and its interface by name."""
    module = importlib.import_module("packages.access.sync.application")

    assert hasattr(module, "AccessSyncApplicationService")
    assert hasattr(module, "AccessSynchronizer")


@pytest.mark.unit
def test_sync_providers_return_annotation_uses_application_service() -> None:
    """Provider return annotations should reference AccessSyncApplicationService."""
    providers_module = importlib.import_module("packages.access.sync.providers")
    application_module = importlib.import_module("packages.access.sync.application")

    return_type = get_type_hints(providers_module.get_access_sync_coordinator)["return"]

    assert return_type is application_module.AccessSyncApplicationService


@pytest.mark.unit
def test_sync_ingress_dependency_uses_access_synchronizer() -> None:
    """Shared ingress types its coordinator as the ``AccessSynchronizer`` interface."""
    ingress_module = importlib.import_module("packages.access.sync.interactions.ingress")

    coordinator_type = get_type_hints(ingress_module.enqueue_user_sync)["coordinator"]

    assert coordinator_type.__name__ == "AccessSynchronizer"
