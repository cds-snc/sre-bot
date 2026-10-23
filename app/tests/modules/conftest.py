"""Fixtures shared by the legacy module tests."""

from collections.abc import Callable

import pytest

from contracts.configuration import HostInfo, install_host_info


@pytest.fixture
def set_environment() -> Callable[[str], None]:
    """Install a HostInfo with the given environment; the autouse fixture removes it after the test."""

    def _set_environment(value: str) -> None:
        install_host_info(HostInfo(environment=value, git_sha="test-sha", public_base_url="http://127.0.0.1:8000"))  # type: ignore[arg-type]

    return _set_environment
