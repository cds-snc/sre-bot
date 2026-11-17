"""Pinning tests for the retired ``/sre incident create`` subcommand.

Each test sends ``/sre incident ...`` from the incident channel through
``slack_bolt.App.dispatch`` over the legacy surface harness, whose external
edges (Slack Web API, ``response_url``, the incidents table, Drive, Docs and
Sheets) are fakes seeded with one incident, its report and its list row.

``create resources`` and the ``create new`` stub are retired with no target
(decisions/migration.md step 4, kind (d), TASK-145.8.6, after a production
usage count). A user who types any ``create`` form now gets the dispatcher's
unknown-command line, which points at the help, and the help no longer lists
``create``. Nothing is written: the tests read back every faked edge and
assert it is unchanged, so a stray recreate path cannot hide behind the reply.
These pins are deleted with the legacy dispatcher by TASK-145.13.
"""

import copy
import re
from typing import Any

import pytest

from .conftest import IncidentSurface

pytestmark = pytest.mark.integration

UNKNOWN_CREATE = "Unknown command: create. Type `/sre incident help` to see a list of commands."


def _edges(surface: IncidentSurface) -> dict[str, Any]:
    """A deep snapshot of every faked edge a recreate would have written."""
    return copy.deepcopy(
        {
            "incidents": surface.table.items(),
            "drive": vars(surface.google.drive),
            "docs": vars(surface.google.docs),
            "sheet": vars(surface.google.sheet),
        }
    )


@pytest.fixture
def seeded(incident_surface: IncidentSurface) -> IncidentSurface:
    """The channel holds one incident with its report and its list row."""
    incident_surface.table.seed()
    incident_surface.google.add_incident_report()
    return incident_surface


@pytest.mark.parametrize("command", ["incident create", "incident create new", "incident create resources"])
def test_every_create_form_answers_the_unknown_command_line_and_writes_nothing(seeded: IncidentSurface, command: str) -> None:
    """Each ``create`` form answers one unknown-command reply; nothing is posted or bookmarked, and no table, Drive, Docs or Sheets state changes."""
    before = _edges(seeded)

    seeded.sre(command)

    assert [message["text"] for message in seeded.slack.responses] == [UNKNOWN_CREATE]
    # The provider's locale lookup is the only Slack call: a read made for every /sre command.
    assert [name for name, _ in seeded.slack.client.calls] == ["users_info"]
    assert _edges(seeded) == before


@pytest.mark.parametrize("command", ["incident help", "incident aide"])
def test_help_no_longer_lists_create(seeded: IncidentSurface, command: str) -> None:
    """The English and French help list neither a ``create`` action nor a ``/sre incident create`` example."""
    seeded.sre(command)

    [message] = seeded.slack.responses
    text = message["text"]
    assert re.search(r"^• create\s", text, flags=re.MULTILINE) is None
    assert "`/sre incident create`" not in text
    # The legacy create-folder form and the products create example are other commands and stay listed.
    assert "• create-folder" in text
    assert '`/sre incident products create "foo bar"`' in text
