"""Incident conversation names: the platform-neutral policy in core.

``incident_conversation_names`` and ``ConversationName`` are pure, so the tests
call them directly. They hold the incident's rule only (environment prefix,
opening date, title, attempts 1 to 5 with a ``-<attempt>`` suffix from the
second); no platform's length or character rules apply here.
"""

from datetime import date

import pytest

from features.incident.core.api import CONVERSATION_NAME_ATTEMPTS, ConversationName, incident_conversation_names

pytestmark = pytest.mark.unit

OPENED_ON = date(2026, 11, 10)


def test_five_candidates_in_attempt_order_for_the_same_title_and_day() -> None:
    names = incident_conversation_names("Panne: base de données", OPENED_ON, production=True)

    assert CONVERSATION_NAME_ATTEMPTS == 5
    assert [name.attempt for name in names] == [1, 2, 3, 4, 5]
    assert {(name.title, name.opened_on, name.production) for name in names} == {("Panne: base de données", OPENED_ON, True)}


@pytest.mark.parametrize(("production", "prefix"), [(True, "incident-2026-11-10"), (False, "incident-dev-2026-11-10")])
def test_the_prefix_names_the_environment_and_the_opening_date(production: bool, prefix: str) -> None:
    assert ConversationName("Database Outage", OPENED_ON, production=production).prefix == prefix


def test_only_attempts_after_the_first_carry_a_suffix() -> None:
    suffixes = [name.suffix for name in incident_conversation_names("x", OPENED_ON, production=True)]

    assert suffixes == ["", "-2", "-3", "-4", "-5"]


def test_the_title_is_kept_as_declared() -> None:
    assert ConversationName("Panne: base de données (prod)!", OPENED_ON, production=True).title == (
        "Panne: base de données (prod)!"
    )


@pytest.mark.parametrize("attempt", [0, CONVERSATION_NAME_ATTEMPTS + 1])
def test_an_attempt_outside_the_bound_is_refused(attempt: int) -> None:
    with pytest.raises(ValueError, match="attempt"):
        ConversationName("x", OPENED_ON, production=True, attempt=attempt)
