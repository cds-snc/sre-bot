"""Incident conversation names: the platform-neutral policy in core.

``incident_conversation_names`` and ``ConversationName`` are pure, so the tests
call them directly. They hold the incident's rule only (environment prefix,
opening date, title, a ``-<attempt>`` suffix from the second attempt); the
number of candidates is the caller's (``[incident_core] conversation_name_attempts``),
passed in. No platform's length or character rules apply here.
"""

from datetime import date

import pytest

from features.incident.core.api import ConversationName, incident_conversation_names

pytestmark = pytest.mark.unit

OPENED_ON = date(2026, 11, 10)


def test_the_given_count_of_candidates_in_attempt_order_for_the_same_title_and_day() -> None:
    names = incident_conversation_names("Panne: base de données", OPENED_ON, production=True, attempts=5)

    assert [name.attempt for name in names] == [1, 2, 3, 4, 5]
    assert {(name.title, name.opened_on, name.production) for name in names} == {("Panne: base de données", OPENED_ON, True)}


@pytest.mark.parametrize(("production", "prefix"), [(True, "incident-2026-11-10"), (False, "incident-dev-2026-11-10")])
def test_the_prefix_names_the_environment_and_the_opening_date(production: bool, prefix: str) -> None:
    assert ConversationName("Database Outage", OPENED_ON, production=production).prefix == prefix


def test_only_attempts_after_the_first_carry_a_suffix() -> None:
    suffixes = [name.suffix for name in incident_conversation_names("x", OPENED_ON, production=True, attempts=5)]

    assert suffixes == ["", "-2", "-3", "-4", "-5"]


def test_the_title_is_kept_as_declared() -> None:
    assert ConversationName("Panne: base de données (prod)!", OPENED_ON, production=True).title == (
        "Panne: base de données (prod)!"
    )


def test_a_single_attempt_is_one_unsuffixed_name() -> None:
    names = incident_conversation_names("x", OPENED_ON, production=True, attempts=1)

    assert [(name.attempt, name.suffix) for name in names] == [(1, "")]


@pytest.mark.parametrize("attempts", [0, -1])
def test_a_count_below_one_is_refused(attempts: int) -> None:
    """A count below one would leave declare no name to try, so it fails before any claim."""
    with pytest.raises(ValueError, match="attempts"):
        incident_conversation_names("x", OPENED_ON, production=True, attempts=attempts)


@pytest.mark.parametrize("attempt", [0, -1])
def test_an_attempt_below_one_is_refused(attempt: int) -> None:
    with pytest.raises(ValueError, match="attempt"):
        ConversationName("x", OPENED_ON, production=True, attempt=attempt)


def test_an_attempt_past_the_default_count_is_a_valid_name() -> None:
    """The upper bound is the configured count the caller passes, not a limit of the name."""
    assert ConversationName("x", OPENED_ON, production=True, attempt=6).suffix == "-6"
