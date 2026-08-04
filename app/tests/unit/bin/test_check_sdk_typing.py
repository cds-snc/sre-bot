"""Behavior tests for SDK typing guardrail and stub dependency wiring."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[3]


def _pyproject_data() -> dict:
    return tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _dev_dependencies() -> list[str]:
    data = _pyproject_data()
    return data["dependency-groups"]["dev"]


def _runtime_dependencies() -> list[str]:
    data = _pyproject_data()
    return data["project"]["dependencies"]


def test_check_sdk_typing_checker_module_exists() -> None:
    spec = importlib.util.find_spec("bin.check_sdk_typing")

    assert spec is not None


def test_sdk_typing_baseline_file_exists() -> None:
    baseline = APP_ROOT / "bin" / "baselines" / "sdk_typing_antipatterns.txt"

    assert baseline.exists()


def test_makefile_has_check_sdk_typing_target() -> None:
    makefile_text = (APP_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "check-sdk-typing:" in makefile_text


def test_pyproject_dev_dependencies_include_sdk_stub_packages() -> None:
    dev_deps = _dev_dependencies()

    assert any(dep.startswith("types-boto3[") for dep in dev_deps)
    assert any(dep.startswith("google-api-python-client-stubs") for dep in dev_deps)


def test_pyproject_runtime_dependencies_do_not_include_sdk_stub_packages() -> None:
    runtime_deps = _runtime_dependencies()

    assert all(not dep.startswith("types-boto3") for dep in runtime_deps)
    assert all(not dep.startswith("google-api-python-client-stubs") for dep in runtime_deps)
