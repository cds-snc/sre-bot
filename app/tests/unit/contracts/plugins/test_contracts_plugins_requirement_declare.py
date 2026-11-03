"""Unit tests for the ``Requirement`` value a plugin returns from ``register_requirements``.

The value is built directly; the assertions read its public surface only: the dotted
setting path it names, value equality and immutability.
"""

import dataclasses

import pytest

from contracts.plugins.requirements import Requirement

pytestmark = pytest.mark.unit


def test_requirement_names_the_setting_path() -> None:
    assert Requirement("slack.tenant").setting == "slack.tenant"


def test_requirements_with_the_same_setting_are_equal_and_hashable() -> None:
    assert Requirement("openai.tenant") == Requirement("openai.tenant")
    assert len({Requirement("openai.tenant"), Requirement("openai.tenant")}) == 1


def test_requirement_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Requirement("slack.tenant").setting = "other"  # type: ignore[misc]
