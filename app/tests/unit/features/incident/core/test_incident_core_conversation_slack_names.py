"""Slack channel names rendered from a ConversationName under Slack's rules.

``slack_channel_name`` is pure, so the tests call it directly. The first attempt
must equal the name the declare pin expects for a plain title (environment
prefix, date, title slug, cut to 80); every attempt must be a valid, distinct
Slack channel name ending in its own suffix.
"""

import re
from datetime import date

import pytest

from features.incident.core.adapters.slack import slack_channel_name
from features.incident.core.api import CONVERSATION_NAME_ATTEMPTS, ConversationName, incident_conversation_names

pytestmark = pytest.mark.unit

OPENED_ON = date(2026, 11, 10)
_SLACK_NAME = re.compile(r"^[a-z0-9_-]{1,80}$")


def _rendered(title: str, *, production: bool = True) -> list[str]:
    return [slack_channel_name(name) for name in incident_conversation_names(title, OPENED_ON, production=production)]


@pytest.mark.parametrize(("production", "prefix"), [(True, "incident-"), (False, "incident-dev-")])
def test_the_first_name_is_the_pinned_legacy_format(production: bool, prefix: str) -> None:
    assert _rendered("Database Outage", production=production)[0] == f"{prefix}2026-11-10-database-outage"


def test_later_attempts_end_two_to_five() -> None:
    assert _rendered("Database Outage") == [
        "incident-2026-11-10-database-outage",
        "incident-2026-11-10-database-outage-2",
        "incident-2026-11-10-database-outage-3",
        "incident-2026-11-10-database-outage-4",
        "incident-2026-11-10-database-outage-5",
    ]


@pytest.mark.parametrize("length", [59, 100])
def test_long_titles_are_cut_to_80_with_the_suffix_kept(length: int) -> None:
    title = "a" * length

    names = _rendered(title, production=False)

    assert names[0] == f"incident-dev-2026-11-10-{title}"[:80]
    assert all(len(name) <= 80 for name in names)
    assert [name.rsplit("-", 1)[1] for name in names[1:]] == ["2", "3", "4", "5"]


def test_characters_slack_refuses_become_single_dashes_and_accents_are_dropped() -> None:
    assert _rendered("Panne: base de données (prod)!")[0] == "incident-2026-11-10-panne-base-de-donnees-prod"


def test_a_title_of_punctuation_only_still_names_a_channel() -> None:
    assert _rendered("?!")[0] == "incident-2026-11-10"


@pytest.mark.parametrize("title", ["Database Outage", "Panne: données", "x" * 120, "  spaced   out  "])
def test_every_attempt_is_a_valid_distinct_slack_name(title: str) -> None:
    names = _rendered(title)

    assert len(names) == CONVERSATION_NAME_ATTEMPTS
    assert len(set(names)) == len(names)
    assert all(_SLACK_NAME.match(name) for name in names)


def test_a_single_name_renders_the_same_whatever_list_it_came_from() -> None:
    assert slack_channel_name(ConversationName("Database Outage", OPENED_ON, production=True, attempt=3)) == (
        "incident-2026-11-10-database-outage-3"
    )
