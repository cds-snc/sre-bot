"""Unit tests for the incident severity vocabulary.

Plain value tests: five levels, 0 (most severe) to 4, ordered by level. There
is no member for an unset severity; the record stores None instead.
"""

import pytest

from features.incident.common.vocabulary import Severity

pytestmark = pytest.mark.unit


def test_levels_run_from_zero_to_four() -> None:
    """The scale is wide enough for teams that use different scales."""
    assert [(level.name, level.value) for level in Severity] == [
        ("SEV0", 0),
        ("SEV1", 1),
        ("SEV2", 2),
        ("SEV3", 3),
        ("SEV4", 4),
    ]


def test_levels_compare_by_number() -> None:
    """A lower number is a more severe level, so levels sort as integers."""
    assert Severity.SEV0 < Severity.SEV1 < Severity.SEV4


def test_there_is_no_level_five() -> None:
    """A value outside the scale is rejected rather than stored."""
    with pytest.raises(ValueError, match="5"):
        Severity(5)
