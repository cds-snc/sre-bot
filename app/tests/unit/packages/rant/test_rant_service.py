"""Tests for rant business logic."""

import pytest

from packages.rant.service import format_rant


@pytest.mark.unit
def test_format_rant_uppercases_and_bolds():
    """Text is uppercased and wrapped in Slack bold markers."""
    assert format_rant("deploys keep failing") == "*DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_format_rant_preserves_numbers_and_symbols():
    """Non-alphabetic characters pass through unchanged."""
    assert format_rant("500 errors @ 3am!") == "*500 ERRORS @ 3AM!*"
