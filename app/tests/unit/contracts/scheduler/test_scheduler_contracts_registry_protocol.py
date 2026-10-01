"""Unit tests for the scheduler registry Protocol in contracts.scheduler.

A Protocol-conformant fake registry stands in for the scheduler runtime: the
tests assign it to the Protocol type (checked statically by mypy) and register
jobs through it, so a feature written against the contract works with any
implementation. An AST scan of the package source proves the contract imports
only the standard library.
"""

import ast
import inspect
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

import contracts.scheduler
from contracts.scheduler.registry import BackgroundJobRegistry

pytestmark = pytest.mark.unit


class _FakeRegistry:
    """Records every registration it receives."""

    def __init__(self) -> None:
        self.daily: list[tuple[str, str, Callable[[], None]]] = []
        self.interval: list[tuple[str, timedelta, Callable[[], None]]] = []

    def register_daily(self, *, job_name: str, schedule: str, job: Callable[[], None]) -> None:
        self.daily.append((job_name, schedule, job))

    def register_interval(self, *, job_name: str, every: timedelta, job: Callable[[], None]) -> None:
        self.interval.append((job_name, every, job))


def _job() -> None:
    return None


def test_fake_registry_satisfies_the_protocol_and_records_registrations() -> None:
    fake = _FakeRegistry()
    registry: BackgroundJobRegistry = fake

    registry.register_daily(job_name="daily", schedule="05:00", job=_job)
    registry.register_interval(job_name="often", every=timedelta(minutes=5), job=_job)

    assert fake.daily == [("daily", "05:00", _job)]
    assert fake.interval == [("often", timedelta(minutes=5), _job)]


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("register_daily", ["self", "job_name", "schedule", "job"]),
        ("register_interval", ["self", "job_name", "every", "job"]),
    ],
)
def test_registry_methods_take_keyword_only_arguments(method: str, expected: list[str]) -> None:
    params = inspect.signature(getattr(BackgroundJobRegistry, method)).parameters

    assert list(params) == expected
    assert all(param.kind is inspect.Parameter.KEYWORD_ONLY for name, param in params.items() if name != "self")


def test_contracts_scheduler_imports_only_the_standard_library() -> None:
    package_dir = Path(contracts.scheduler.__file__).parent
    offenders: list[str] = []
    for source in sorted(package_dir.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            offenders.extend(
                f"{source.name}: {module}" for module in modules if module.split(".")[0] not in sys.stdlib_module_names
            )

    assert offenders == []
