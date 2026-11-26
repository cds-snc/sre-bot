"""Unit tests for an instance destination as a workplace reference.

A destination records its system and tenant beside the conversation id, never a bare
vendor id (decisions/workplace-systems.md rule 4), so a poster is chosen by system and
the language policy is asked about the right conversation. Built directly, no stubs.
"""

import pytest

from capabilities.webhooks.domain.kinds import Destination
from contracts.workplace import WorkplaceSystem

pytestmark = pytest.mark.unit


def test_a_destination_names_its_system_tenant_and_conversation() -> None:
    """The three parts of the reference are kept as given; triage defaults to off."""
    destination = Destination(system=WorkplaceSystem.SLACK, tenant="T123", conversation_id="C123")

    assert (destination.system, destination.tenant, destination.conversation_id) == (WorkplaceSystem.SLACK, "T123", "C123")
    assert destination.triage is False


def test_a_system_outside_the_closed_set_is_refused() -> None:
    """A plain string is not a workplace system, so a typo never reaches a poster lookup."""
    with pytest.raises(ValueError, match="system"):
        Destination(system="slack", tenant="T123", conversation_id="C123")  # type: ignore[arg-type]


@pytest.mark.parametrize(("tenant", "conversation_id"), [("", "C123"), ("T123", ""), ("  ", "C123")])
def test_a_blank_tenant_or_conversation_is_refused(tenant: str, conversation_id: str) -> None:
    """A reference without its tenant or vendor id is the bare id rule 4 forbids."""
    with pytest.raises(ValueError):
        Destination(system=WorkplaceSystem.SLACK, tenant=tenant, conversation_id=conversation_id)
