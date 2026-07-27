"""Contract tests for the idempotency package public surface after legacy removal.

These assertions guard observable import behavior: legacy cache/service modules
and symbols should no longer be importable once the package is contracted to the
claim/complete/release primitive.
"""

from __future__ import annotations

import importlib.util

import pytest

import infrastructure.idempotency as idempotency
from infrastructure.idempotency import dynamodb, factory, protocol

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "module_name",
    [
        "infrastructure.idempotency.cache",
        "infrastructure.idempotency.service",
    ],
)
def test_legacy_modules_are_not_discoverable(module_name: str) -> None:
    """Legacy idempotency modules are removed from the import graph."""
    assert importlib.util.find_spec(module_name) is None


@pytest.mark.parametrize(
    "symbol_name",
    [
        "IdempotencyCache",
        "DynamoDBCache",
        "IdempotencyService",
        "DynamoDBIdempotencyService",
        "get_cache",
        "reset_cache",
        "get_idempotency_service",
    ],
)
def test_public_package_no_longer_exports_legacy_symbols(symbol_name: str) -> None:
    """Top-level package exports only the active idempotency surface."""
    assert not hasattr(idempotency, symbol_name)


def test_factory_module_no_longer_provides_legacy_cache_builders() -> None:
    """Factory helpers expose only store-oriented constructors."""
    assert not hasattr(factory, "get_cache")
    assert not hasattr(factory, "reset_cache")
    assert not hasattr(factory, "get_idempotency_service")


def test_protocol_module_no_longer_exposes_legacy_service_protocol() -> None:
    """Protocol layer retains only claim/complete/release contracts."""
    assert not hasattr(protocol, "IdempotencyService")


def test_dynamodb_module_no_longer_exposes_legacy_cache_class() -> None:
    """DynamoDB adapter keeps only the idempotency store implementation."""
    assert not hasattr(dynamodb, "DynamoDBCache")
