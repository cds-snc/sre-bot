"""Unit tests for the WorkplaceSystem vocabulary in the workplace contract.

Plain value tests: the closed set of systems a stored reference or a policy
setting may name, and their stored strings. An unknown value raises, because a
system is validated strictly where it is chosen.
"""

import pytest

import contracts.workplace
from contracts.workplace import WorkplaceSystem

pytestmark = pytest.mark.unit


def test_the_package_root_exports_the_vocabulary_and_the_configured_systems_read() -> None:
    """The package root is the stable import path for the vocabulary and the read."""
    assert contracts.workplace.__all__ == ["ConfiguredSystems", "WorkplaceSystem"]


def test_members_are_the_supported_systems_with_their_stored_values() -> None:
    """Each member's value is the string stored on references and read from settings."""
    assert {member.name: member.value for member in WorkplaceSystem} == {"SLACK": "slack", "GOOGLE": "google"}


def test_an_unknown_system_is_rejected() -> None:
    """A value outside the closed set never becomes a member."""
    with pytest.raises(ValueError, match="teams"):
        WorkplaceSystem("teams")
