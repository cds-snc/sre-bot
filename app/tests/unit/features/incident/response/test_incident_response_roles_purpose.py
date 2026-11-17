"""``purpose_with_roles``: the channel purpose's ``IC: ... / OL: ...`` line, spaced as the legacy command wrote it."""

import pytest

from features.incident.response.service.roles import purpose_with_roles

pytestmark = pytest.mark.unit


def test_a_purpose_without_the_line_gets_it_appended_after_a_space_and_a_newline() -> None:
    assert purpose_with_roles("Checkout outage", "U1", "U2") == "Checkout outage \nIC: <@U1> / OL: <@U2>"


def test_an_empty_purpose_keeps_the_leading_space() -> None:
    assert purpose_with_roles("", "U1", "U2") == " \nIC: <@U1> / OL: <@U2>"


def test_an_existing_line_is_replaced_by_a_newline_and_the_new_one() -> None:
    purpose = purpose_with_roles("Checkout outage\nIC: <@U0OLDIC> / OL: <@U0OLDOL>", "U1", "U2")

    assert purpose == "Checkout outage\n\nIC: <@U1> / OL: <@U2>"


def test_text_after_the_replaced_line_is_kept() -> None:
    assert purpose_with_roles("IC: <@U0A> / OL: <@U0B> tail", "U1", "U2") == "\nIC: <@U1> / OL: <@U2> tail"


def test_the_result_is_cut_to_250_characters() -> None:
    assert purpose_with_roles("x" * 300, "U1", "U2") == "x" * 250
