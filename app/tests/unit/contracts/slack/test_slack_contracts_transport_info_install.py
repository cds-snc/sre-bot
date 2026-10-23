"""Unit tests for SlackTransportInfo in contracts.slack.transport: the transport facts the host installs.

The legacy modules read the command prefix from it, so they never import the
host's transport slice. The root conftest installs one per test; these tests
install and remove their own to observe the accessor.
"""

import dataclasses

import pytest

from contracts.configuration import ConfigurationError
from contracts.slack.transport import (
    SlackTransportInfo,
    install_slack_transport_info,
    slack_transport_info,
    uninstall_slack_transport_info,
)

pytestmark = pytest.mark.unit


def test_transport_info_is_frozen() -> None:
    """Assigning to an installed fact raises, so no reader can change it for the others."""
    info = SlackTransportInfo(command_prefix="dev-")

    with pytest.raises(dataclasses.FrozenInstanceError):
        info.command_prefix = "other"  # type: ignore[misc]


def test_accessor_returns_the_installed_object() -> None:
    """The accessor hands back exactly the installed facts."""
    info = SlackTransportInfo(command_prefix="dev-")

    install_slack_transport_info(info)

    assert slack_transport_info() is info


def test_install_replaces_the_previous_info() -> None:
    """A second install replaces the first, so the factory can run again in one process."""
    install_slack_transport_info(SlackTransportInfo(command_prefix="first-"))
    install_slack_transport_info(SlackTransportInfo(command_prefix="second-"))

    assert slack_transport_info().command_prefix == "second-"


def test_accessor_before_install_names_the_factory() -> None:
    """Reading the facts before the configuration phase ran fails with the fix in the message."""
    uninstall_slack_transport_info()

    with pytest.raises(ConfigurationError, match="create_app"):
        slack_transport_info()
