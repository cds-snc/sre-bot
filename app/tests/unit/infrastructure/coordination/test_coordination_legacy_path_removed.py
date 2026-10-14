"""Contract tests for the coordination package public surface after the idempotency path removal.

These assertions guard observable import behavior: the old idempotency
package path and the legacy cache/service modules are not importable, and the
coordination package exports implementations without re-exporting the
contract types.
"""

import importlib.util

import pytest

import infrastructure.coordination as coordination
from infrastructure.coordination import dynamodb, factory

pytestmark = pytest.mark.unit

OLD_PACKAGE = ".".join(("infrastructure", "idempotency"))


def test_old_idempotency_package_is_not_discoverable() -> None:
    """The old package path resolves to nothing, not even a namespace package."""
    assert importlib.util.find_spec(OLD_PACKAGE) is None


@pytest.mark.parametrize("module_name", ["cache", "service"])
def test_legacy_modules_are_not_discoverable(module_name: str) -> None:
    """Legacy cache and service modules do not exist in the coordination package."""
    assert importlib.util.find_spec(f"infrastructure.coordination.{module_name}") is None


@pytest.mark.parametrize("symbol_name", ["ConditionalWriteStore", "ClaimResult", "ClaimOutcome"])
def test_package_does_not_reexport_contract_names(symbol_name: str) -> None:
    """Contract types are imported from contracts.coordination, never from infrastructure."""
    assert not hasattr(coordination, symbol_name)
    assert symbol_name not in coordination.__all__


@pytest.mark.parametrize(
    "symbol_name",
    [
        "".join(("Idempotency", "Cache")),
        "".join(("DynamoDB", "Cache")),
        "".join(("Idempotency", "Service")),
        "".join(("DynamoDB", "Idempotency", "Service")),
        "_".join(("get", "cache")),
        "_".join(("reset", "cache")),
        "_".join(("get", "idempotency", "service")),
    ],
)
def test_public_package_no_longer_exports_legacy_symbols(symbol_name: str) -> None:
    """Top-level package exports only the active conditional-write surface."""
    assert not hasattr(coordination, symbol_name)


def test_factory_module_no_longer_provides_legacy_cache_builders() -> None:
    """Factory helpers expose only store-oriented constructors."""
    assert not hasattr(factory, "_".join(("get", "cache")))
    assert not hasattr(factory, "_".join(("reset", "cache")))
    assert not hasattr(factory, "_".join(("get", "idempotency", "service")))


def test_dynamodb_module_no_longer_exposes_legacy_cache_class() -> None:
    """DynamoDB adapter keeps only the conditional-write store implementation."""
    assert not hasattr(dynamodb, "".join(("DynamoDB", "Cache")))
