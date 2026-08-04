"""Fail-first naming tests for Sprint 1 Access Sync application service symbols."""

import importlib
from typing import get_type_hints

import pytest


@pytest.mark.unit
def test_sync_application_module_exports_application_service_symbols() -> None:
    """Application module should expose the renamed service symbols."""
    module = importlib.import_module("packages.access.sync.application")

    assert hasattr(module, "AccessSyncApplicationService")
    assert hasattr(module, "AccessSyncApplicationServicePort")


@pytest.mark.unit
def test_sync_providers_return_annotation_uses_application_service() -> None:
    """Provider return annotations should reference AccessSyncApplicationService."""
    providers_module = importlib.import_module("packages.access.sync.providers")
    application_module = importlib.import_module("packages.access.sync.application")

    return_type = get_type_hints(providers_module.get_access_sync_coordinator)["return"]

    assert return_type is application_module.AccessSyncApplicationService


@pytest.mark.unit
def test_sync_ingress_dependency_uses_application_service_port() -> None:
    """Shared ingress should accept the renamed application service protocol."""
    ingress_module = importlib.import_module("packages.access.sync.interactions.ingress")

    coordinator_type = get_type_hints(ingress_module.enqueue_user_sync)["coordinator"]

    assert coordinator_type.__name__ == "AccessSyncApplicationServicePort"
