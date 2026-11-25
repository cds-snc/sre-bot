"""Behavior tests for MultilingualText, the platform-neutral message in several languages.

The value is built from an ordered list of languages and a function rendering
one line per language, so the tests pass plain lambdas and literal texts; no
translator is involved. plain_text() is the fallback every platform can show,
so its exact output (one line per language, in the given order) is asserted.
"""

import pytest

from contracts.languages import MultilingualText

pytestmark = pytest.mark.unit


def test_of_renders_one_part_per_language_in_the_given_order() -> None:
    """French first in, French first out: the order is the caller's, never re-sorted."""
    text = MultilingualText.of(("fr-FR", "en-US"), lambda language: f"line {language}")

    assert text.parts == (("fr-FR", "line fr-FR"), ("en-US", "line en-US"))


def test_plain_text_puts_each_language_on_its_own_line() -> None:
    """The fallback layout is one line per language, top to bottom."""
    text = MultilingualText((("en-US", "Status changed"), ("fr-FR", "Statut changé")))

    assert text.plain_text() == "Status changed\nStatut changé"


def test_a_single_language_is_its_own_line() -> None:
    """A one-language instance posts exactly that line, with no separator."""
    assert MultilingualText.of(("en-US",), lambda _: "Only English").plain_text() == "Only English"


def test_an_empty_message_is_refused() -> None:
    """A message with no language would post nothing; it is a programming error."""
    with pytest.raises(ValueError, match="at least one language"):
        MultilingualText(())


def test_a_repeated_language_is_refused() -> None:
    """Each language appears once, so a reader never sees the same text twice."""
    with pytest.raises(ValueError, match="en-US"):
        MultilingualText((("en-US", "a"), ("en-US", "b")))
