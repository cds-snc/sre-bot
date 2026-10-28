"""The unused retry store, retry worker, resilience service and circuit breaker are deleted.

Imports each retired module and expects ``ModuleNotFoundError``, so a reintroduced copy of the
package or of ``RetrySettings`` fails here instead of growing a second retry mechanism beside
``QueueService``.
"""

import importlib

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "module",
    [
        "infrastructure.resilience",
        "infrastructure.resilience.circuit_breaker",
        "infrastructure.resilience.retry",
        "infrastructure.resilience.service",
        "infrastructure.configuration.infrastructure",
        "infrastructure.configuration.infrastructure.retry",
    ],
)
def test_retired_resilience_modules_no_longer_exist(module: str) -> None:
    """The resilience package and the retry settings module cannot be imported."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
