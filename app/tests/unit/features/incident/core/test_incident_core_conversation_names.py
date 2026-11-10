"""Incident conversation names: the legacy format, made safe for Slack, with bounded numbered suffixes.

``incident_conversation_names`` is pure, so the tests call it directly. The
first candidate must equal the name the declare pin expects for a plain title
(environment prefix, date, title slug, cut to 80); every candidate must be a
valid Slack channel name; the suffixes run ``-2`` to ``-5``.
"""

import re
from datetime import date

import pytest

from features.incident.core.api import CONVERSATION_NAME_ATTEMPTS, incident_conversation_names

pytestmark = pytest.mark.unit

OPENED_ON = date(2026, 11, 10)
_SLACK_NAME = re.compile(r"^[a-z0-9_-]{1,80}$")


@pytest.mark.parametrize(("production", "prefix"), [(True, "incident-"), (False, "incident-dev-")])
def test_the_first_name_is_the_pinned_legacy_format(production: bool, prefix: str) -> None:
    names = incident_conversation_names("Database Outage", OPENED_ON, production=production)

    assert names[0] == f"{prefix}2026-11-10-database-outage"


def test_later_names_take_suffixes_two_to_five() -> None:
    names = incident_conversation_names("Database Outage", OPENED_ON, production=True)

    assert CONVERSATION_NAME_ATTEMPTS == 5
    assert names == (
        "incident-2026-11-10-database-outage",
        "incident-2026-11-10-database-outage-2",
        "incident-2026-11-10-database-outage-3",
        "incident-2026-11-10-database-outage-4",
        "incident-2026-11-10-database-outage-5",
    )


@pytest.mark.parametrize("length", [59, 100])
def test_long_titles_are_cut_to_80_with_the_suffix_kept(length: int) -> None:
    title = "a" * length

    names = incident_conversation_names(title, OPENED_ON, production=False)

    assert names[0] == f"incident-dev-2026-11-10-{title}"[:80]
    assert all(len(name) <= 80 for name in names)
    assert [name.rsplit("-", 1)[1] for name in names[1:]] == ["2", "3", "4", "5"]


def test_characters_slack_refuses_become_single_dashes_and_accents_are_dropped() -> None:
    [first, *_] = incident_conversation_names("Panne: base de données (prod)!", OPENED_ON, production=True)

    assert first == "incident-2026-11-10-panne-base-de-donnees-prod"


def test_a_title_of_punctuation_only_still_names_a_channel() -> None:
    [first, *_] = incident_conversation_names("?!", OPENED_ON, production=True)

    assert first == "incident-2026-11-10"


@pytest.mark.parametrize("title", ["Database Outage", "Panne: données", "x" * 120, "  spaced   out  "])
def test_every_candidate_is_a_valid_distinct_slack_name(title: str) -> None:
    names = incident_conversation_names(title, OPENED_ON, production=True)

    assert len(names) == CONVERSATION_NAME_ATTEMPTS
    assert len(set(names)) == len(names)
    assert all(_SLACK_NAME.match(name) for name in names)
