"""Unit tests for HostInfo in contracts.configuration: a frozen fact set the app factory installs."""

import dataclasses
from typing import Literal, get_args, get_type_hints

import pytest

from contracts.configuration import ConfigurationError, HostInfo, host_info, install_host_info, uninstall_host_info

pytestmark = pytest.mark.unit


def _info(**overrides: str) -> HostInfo:
    values = {"environment": "ci", "git_sha": "abc123", "public_base_url": "http://127.0.0.1:8000", **overrides}
    return HostInfo(**values)  # type: ignore[arg-type]


def test_host_info_is_frozen() -> None:
    """Assigning to an installed fact raises, so no layer can change it for the others."""
    info = _info()

    with pytest.raises(dataclasses.FrozenInstanceError):
        info.git_sha = "other"  # type: ignore[misc]


def test_accessor_returns_the_installed_object() -> None:
    """The accessor hands back exactly the installed HostInfo."""
    info = _info()

    install_host_info(info)

    assert host_info() is info


def test_install_replaces_the_previous_info() -> None:
    """A second install replaces the first, so the factory can run again in one process."""
    install_host_info(_info(git_sha="first"))
    install_host_info(_info(git_sha="second"))

    assert host_info().git_sha == "second"


def test_accessor_before_install_names_the_factory() -> None:
    """Reading host facts before the factory ran fails with the fix in the message."""
    uninstall_host_info()

    with pytest.raises(ConfigurationError, match="create_app"):
        host_info()


def test_accessor_after_uninstall_fails_again() -> None:
    """Removing the facts makes the accessor fail again."""
    install_host_info(_info())
    uninstall_host_info()

    with pytest.raises(ConfigurationError):
        host_info()


def test_environment_is_the_three_environment_literal() -> None:
    """The annotation lists exactly the environments that have a configuration file."""
    annotation = get_type_hints(HostInfo)["environment"]

    assert Literal is not None
    assert set(get_args(annotation)) == {"local", "ci", "production"}
